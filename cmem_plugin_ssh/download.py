"""SSH download files task plugin"""

import tempfile
from collections.abc import Sequence
from pathlib import Path

import paramiko
from cmem_plugin_base.dataintegration.context import (
    ExecutionContext,
    ExecutionReport,
)
from cmem_plugin_base.dataintegration.description import Icon, Plugin, PluginAction, PluginParameter
from cmem_plugin_base.dataintegration.entity import Entities, Entity, EntitySchema
from cmem_plugin_base.dataintegration.parameter.choice import ChoiceParameterType
from cmem_plugin_base.dataintegration.parameter.password import Password, PasswordParameterType
from cmem_plugin_base.dataintegration.plugins import WorkflowPlugin
from cmem_plugin_base.dataintegration.ports import FixedNumberOfInputs, FixedSchemaPort
from cmem_plugin_base.dataintegration.typed_entities.file import FileEntitySchema, LocalFile
from paramiko import SFTPAttributes

from cmem_plugin_ssh.autocompletion import DirectoryParameterType
from cmem_plugin_ssh.list import generate_list_schema
from cmem_plugin_ssh.retrieval import SSHRetrieval
from cmem_plugin_ssh.utils import (
    AUTHENTICATION_CHOICES,
    ERROR_HANDLING_CHOICES,
    load_private_key,
    preview_results,
    setup_max_workers,
)


@Plugin(
    label="Download SSH files",
    plugin_id="cmem_plugin_ssh-Download",
    description="Download files from an SSH server.",
    documentation="""
Downloads files from an SSH server into the workflow.

What is downloaded depends on the input port. When nothing is connected, the task lists
the configured directory itself and downloads the files matching the regular
expression. When a file listing is connected, it downloads exactly the paths carried in
the `file_name` value of the incoming entities, and the directory, regular expression
and subfolder settings are then without effect. Either way the files leave the output
port as file entities, stored in a temporary directory on the eccenca Corporate Memory
host from where the following tasks read them.

**List SSH files** produces the listing this task accepts, so a workflow can list
first, narrow the result down and download only what is left. **Upload SSH files**
covers the other direction.

The **Preview results** action lists the first ten files that a run without input would
download, without running the workflow.

#### Caveats

* Only the plain file name of a remote file is kept. Downloaded files of the same name
coming from different folders overwrite each other, and just one of them reaches the
output port.
* A file that cannot be read is dropped from the output silently with both Ignore and
Warning. The warning names the unreadable files seen while listing, which is not
necessarily the same set of files.
* A folder that cannot be read is skipped silently unless the error handling is set to
Error, and the files below it are then never downloaded.
* The task logs in with the configured credentials only, and offers no key of the
machine it runs on. The host key of the server in turn is accepted as presented and
never checked against a known hosts list.
* Establishing the connection fails after 20 seconds.
    """,
    icon=Icon(package=__package__, file_name="ssh-icon.svg"),
    actions=[
        PluginAction(
            name="preview_results",
            label="Preview results (max. 10)",
            description="Connect to the server and list the first ten matching files.",
        ),
    ],
    parameters=[
        PluginParameter(
            name="hostname",
            label="Hostname",
            description="Host name or IP address of the SSH server.",
        ),
        PluginParameter(
            name="port",
            label="Port",
            description="TCP port the SSH server listens on.",
            default_value=22,
        ),
        PluginParameter(
            name="username",
            label="Username",
            description="Account to log in as.",
        ),
        PluginParameter(
            name="authentication_method",
            label="Authentication method",
            description="How the task authenticates against the server.",
            param_type=ChoiceParameterType(AUTHENTICATION_CHOICES),
            default_value="password",
        ),
        PluginParameter(
            name="private_key",
            label="Private key",
            description="Private key in PEM format, used when the authentication method is Key. "
            "RSA, ECDSA and Ed25519 keys are supported.",
            param_type=PasswordParameterType(),
            default_value="",
        ),
        PluginParameter(
            name="password",
            label="Password",
            description="Password of the account, or the passphrase of the private key when the "
            "authentication method is Key.",
            param_type=PasswordParameterType(),
            default_value="",
        ),
        PluginParameter(
            name="path",
            label="Path",
            description=(
                "Remote directory the files are downloaded from, and ignored when a file"
                " listing arrives on the input port. Autocompletion starts in the home"
                " directory of the account, use '..' for the parent directory"
                " or '/' for the root directory."
            ),
            default_value="",
            param_type=DirectoryParameterType("directories", "Folder"),
        ),
        PluginParameter(
            name="regex",
            label="Regular expression",
            description="Regular expression a file name has to match completely to be "
            "downloaded. It is matched against the plain file name, not against the path.",
            default_value="^.*$",
        ),
        PluginParameter(
            name="error_handling",
            label="Error handling",
            description="How the task reacts to files and folders the account cannot read.",
            param_type=ChoiceParameterType(ERROR_HANDLING_CHOICES),
            default_value="error",
        ),
        PluginParameter(
            name="no_subfolder",
            label="No subfolder",
            description="If enabled, only the given directory is searched and its subfolders are "
            "left out.",
            default_value=False,
        ),
        PluginParameter(
            name="max_workers",
            label="Maximum number of workers",
            description="Number of threads the Preview results action uses to list subfolders in "
            "parallel, from 1 to 32. A workflow run always lists with a single thread. Too many "
            "parallel channels make some servers refuse them with a ChannelException.",
            default_value=1,
            advanced=True,
        ),
    ],
)
class DownloadFiles(WorkflowPlugin):
    """SSH Workflow Plugin: File download"""

    ssh_client: paramiko.SSHClient
    sftp: paramiko.SFTPClient

    def __init__(  # noqa: PLR0913 PLR0917
        self,
        hostname: str,
        port: int,
        username: str,
        authentication_method: str,
        private_key: str | Password,
        password: str | Password,
        path: str,
        error_handling: str,
        no_subfolder: bool,
        regex: str = "",
        max_workers: int = 1,
    ):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.authentication_method = authentication_method
        self.private_key = private_key
        self.password = password if isinstance(password, str) else password.decrypt()
        self.error_handling = error_handling
        self.path = path
        self.no_subfolder = no_subfolder
        self.regex = rf"{regex}"
        self.max_workers = setup_max_workers(max_workers)
        self.input_ports = FixedNumberOfInputs([FixedSchemaPort(schema=generate_list_schema())])
        self.output_port = FixedSchemaPort(schema=FileEntitySchema())
        self.download_dir = tempfile.mkdtemp()

    def establish_ssh_connection(self) -> None:
        """Connect to the ssh client with the selected authentication method"""
        if self.authentication_method == "key":
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                hostname=self.hostname,
                username=self.username,
                pkey=load_private_key(self.private_key, self.password),
                password=self.password,
                port=self.port,
                timeout=20,
                allow_agent=False,
                look_for_keys=False,
            )
        elif self.authentication_method == "password":
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                hostname=self.hostname,
                username=self.username,
                password=self.password,
                port=self.port,
                timeout=20,
                allow_agent=False,
                look_for_keys=False,
            )

    def cleanup_ssh_connections(self) -> None:
        """Close connection from sftp and ssh"""
        self.sftp.close()
        self.ssh_client.close()

    def _initialize_ssh_and_sftp_connections(self) -> None:
        self.ssh_client = paramiko.SSHClient()
        self.establish_ssh_connection()
        self.sftp = self.ssh_client.open_sftp()

    def preview_results(self) -> str:
        """Preview the results of an execution"""
        self._initialize_ssh_and_sftp_connections()
        return preview_results(
            ssh_client=self.ssh_client,
            no_subfolder=self.no_subfolder,
            regex=self.regex,
            path=self.path,
            error_handling=self.error_handling,
            max_workers=self.max_workers,
        )

    def execute(self, inputs: Sequence[Entities], context: ExecutionContext) -> Entities:
        """Execute the workflow task"""
        _ = inputs
        schema = FileEntitySchema()

        self._initialize_ssh_and_sftp_connections()

        context.report.update(
            ExecutionReport(entity_count=0, operation="wait", operation_desc="files listed.")
        )

        if len(inputs) > 0:
            downloaded_files, faulty_files = self.download_with_input(inputs, context)
            entities = [schema.to_entity(file) for file in downloaded_files]
            faulty_entities = [schema.to_entity(file) for file in faulty_files]
            if self.error_handling == "warning" and len(faulty_files) > 0:
                context.report.update(
                    ExecutionReport(
                        entity_count=len(entities),
                        operation="done",
                        operation_desc="entities generated",
                        sample_entities=Entities(
                            entities=iter(faulty_entities), schema=FileEntitySchema()
                        ),
                        warnings=[
                            (
                                "Some files have been ignored that the current user does not "
                                "have access to. "
                                "Those files have been listed below as sample entities."
                            )
                        ],
                    )
                )
            else:
                context.report.update(
                    ExecutionReport(
                        entity_count=len(entities),
                        operation="write",
                        operation_desc="files downloaded",
                        sample_entities=Entities(entities=iter(entities[:10]), schema=schema),
                    )
                )

            return Entities(entities=iter(entities), schema=schema)

        retrieval = SSHRetrieval(
            ssh_client=self.ssh_client,
            no_subfolder=self.no_subfolder,
            regex=self.regex,
        )
        files = retrieval.list_files_parallel(
            files=[],
            context=context,
            path=self.path,
            error_handling=self.error_handling,
            no_access_files=[],
        )
        downloaded_files = self.download_no_input(files)
        entities = [schema.to_entity(file) for file in downloaded_files]

        self.update_context(context, entities, files, schema)

        self.cleanup_ssh_connections()

        return Entities(entities=iter(entities), schema=schema)

    def update_context(
        self,
        context: ExecutionContext,
        entities: list[Entity],
        files: tuple[list[SFTPAttributes], list[SFTPAttributes]],
        schema: EntitySchema,
    ) -> None:
        """Give a context update depending on the selected error handling method"""
        if self.error_handling == "warning" and len(files[1]) > 0:
            faulty_files = files[1]
            faulty_entities = []
            for file in faulty_files:
                faulty_entities.append(  # noqa: PERF401
                    Entity(
                        uri=file.filename,
                        values=[
                            [file.filename],
                            [str(file.st_size)],
                            [str(file.st_uid)],
                            [str(file.st_gid)],
                            [str(file.st_mode)],
                            [str(file.st_atime)],
                            [str(file.st_mtime)],
                        ],
                    )
                )
            context.report.update(
                ExecutionReport(
                    entity_count=len(entities),
                    operation="done",
                    operation_desc="entities generated",
                    sample_entities=Entities(
                        entities=iter(faulty_entities), schema=generate_list_schema()
                    ),
                    warnings=[
                        (
                            "Some files have been listed that the current user does not have "
                            "access to. "
                            "Those files have been listed below as sample entities."
                        )
                    ],
                )
            )

        else:
            context.report.update(
                ExecutionReport(
                    entity_count=len(entities),
                    operation="done",
                    operation_desc="entities generated",
                    sample_entities=Entities(entities=iter(entities[:10]), schema=schema),
                )
            )

    def download_no_input(self, files: tuple[list[SFTPAttributes], list[SFTPAttributes]]) -> list:
        """Download files with no given input"""
        entities = []
        for file in files[0]:
            try:
                remote_path = file.filename
                local_path = self.download_dir / Path(Path(file.filename).name)
                self.sftp.get(remotepath=remote_path, localpath=local_path)
                entities.append(LocalFile(str(local_path)))
            except (PermissionError, OSError) as e:
                if self.error_handling in {"ignore", "warning"}:
                    pass
                else:
                    raise ValueError(f"No access to '{file.filename}': {e}") from e

        return entities

    def download_with_input(
        self, inputs: Sequence[Entities], context: ExecutionContext
    ) -> tuple[list, list]:
        """Download files with a given input"""
        downloaded_entities = []
        faulty_entities = []
        for entity in inputs[0].entities:
            try:
                if context.workflow.status() == "Canceling":
                    break
            except AttributeError:
                pass
            filename = entity.values[0][0]
            try:
                local_path = self.download_dir / Path(Path(filename).name)
                self.sftp.get(remotepath=filename, localpath=local_path)
                downloaded_entities.append(LocalFile(str(local_path)))
            except (PermissionError, OSError) as e:
                if self.error_handling in {"ignore", "warning"}:
                    faulty_entities.append(LocalFile(Path(filename).name))
                else:
                    raise ValueError(f"No access to '{filename}': {e}") from e
            context.report.update(
                ExecutionReport(
                    entity_count=len(downloaded_entities),
                    operation="write",
                    operation_desc="files downloaded",
                )
            )
        return downloaded_entities, faulty_entities
