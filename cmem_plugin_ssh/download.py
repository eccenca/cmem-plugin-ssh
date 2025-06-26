"""SSH download files task plugin"""

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
    description="Download files from a given SSH instance",
    documentation="""
This workflow task downloads files from a specified SSH instance.

By providing the hostname, username, port and authentication method, you can specify the
folder from which the data should be extracted.

You can also define a regular expression to include or exclude specific files.

There is also an option to prevent files in subfolders from being included.

#### Authentication Methods:
* **Password:** Only the password will be used for authentication. The private key field is
ignored, even if filled.
* **Key:** The private key will be used for authentication. If the key is encrypted, the password
will be used to decrypt it.

#### Error handling modes:
* **Ignore:** Ignores the permission rights of files and lists downloads all files it has access to.
Skips folders and files when there is no correct permission.
* **Warning:** Warns the user about files that the user has no permission rights to. Downloads
all other files and skips files folder when there is no correct permission.
* **Error:** Throws an error when there is a single file or folder with incorrect permission rights.

#### Note:
* If a connection cannot be established within 20 seconds, a timeout occurs.
* Currently supported key types are: RSA, DSS, ECDSA, Ed25519.
* Setting the maximum amount of workers to more than 1 may cause a Channel Exception when
the amount of files is too large
    """,
    icon=Icon(package=__package__, file_name="ssh-icon.svg"),
    actions=[
        PluginAction(
            name="preview_results",
            label="Preview results (max. 10)",
            description="Lists 10 files as a preview.",
        ),
    ],
    parameters=[
        PluginParameter(
            name="hostname",
            label="Hostname",
            description="Hostname to connect to. Usually in the form of an IP address",
        ),
        PluginParameter(
            name="port",
            label="Port",
            description="The port on which the connection will be tried on. Default is 22.",
            default_value=22,
        ),
        PluginParameter(
            name="username",
            label="Username",
            description="The username of which a connection will be instantiated.",
        ),
        PluginParameter(
            name="authentication_method",
            label="Authentication method",
            description="The method that is used to connect to the SSH server.",
            param_type=ChoiceParameterType(AUTHENTICATION_CHOICES),
            default_value="password",
        ),
        PluginParameter(
            name="private_key",
            label="Private key",
            description="Your private key to connect via SSH.",
            param_type=PasswordParameterType(),
            default_value="",
        ),
        PluginParameter(
            name="password",
            label="Password",
            description="Depending on your authentication method this will either be used to"
            "connect via password to SSH or is used to decrypt the SSH private key",
            param_type=PasswordParameterType(),
            default_value="",
        ),
        PluginParameter(
            name="path",
            label="Path",
            description="The currently selected path withing your SSH instance.",
            default_value="",
            param_type=DirectoryParameterType("directories", "Folder"),
        ),
        PluginParameter(
            name="regex",
            label="Regular expression",
            description="A regular expression used to define which files will get downloaded.",
            default_value="^.*$",
        ),
        PluginParameter(
            name="error_handling",
            label="Error handling for missing permissions.",
            description="A choice on how to handle errors concerning the permissions rights."
            "When choosing 'ignore' all files get skipped if the current "
            "user has correct permission rights."
            "When choosing 'warning' all files get downloaded however there will be "
            "a mention that some of the files are not under the users permissions"
            "if there are any and these get skipped."
            "When choosing 'error' the files will not get downloaded if there"
            "is even a single file the user has no access to.",
            param_type=ChoiceParameterType(ERROR_HANDLING_CHOICES),
            default_value="error",
        ),
        PluginParameter(
            name="no_subfolder",
            label="No subfolder",
            description="When this flag is set, only files from the current directory "
            "will be downloaded.",
            default_value=False,
        ),
        PluginParameter(
            name="max_workers",
            label="Maximum amount of workers.",
            description="Determines the amount of workers used for concurrent thread execution "
            "of the task. Default is 1, maximum is 32. Note that too many workers can cause a "
            "ChannelException.",
            default_value=1,
            advanced=True,
        ),
    ],
)
class DownloadFiles(WorkflowPlugin):
    """SSH Workflow Plugin: File download"""

    def __init__(  # noqa: PLR0913
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
        self.download_dir = Path()
        self.ssh_client = paramiko.SSHClient()
        self.connect_ssh_client()
        self.sftp = self.ssh_client.open_sftp()

    def connect_ssh_client(self) -> None:
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
            )
        elif self.authentication_method == "password":
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                hostname=self.hostname,
                username=self.username,
                password=self.password,
                port=self.port,
                timeout=20,
            )

    def close_connections(self) -> None:
        """Close connection from sftp and ssh"""
        self.sftp.close()
        self.ssh_client.close()

    def preview_results(self) -> str:
        """Preview the results of an execution"""
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
                            "Some files have been ignored that the current user does not have "
                            "access to. "
                            "Those files have been listed below as sample entities."
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

        self.close_connections()

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
                        "Some files have been listed that the current user does not have access to."
                        "Those files have been listed below as sample entities."
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
                self.sftp.get(
                    remotepath=file.filename, localpath=self.download_dir / Path(file.filename).name
                )
                entities.append(LocalFile(Path(file.filename).name))
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
                self.sftp.get(
                    remotepath=filename, localpath=self.download_dir / Path(filename).name
                )
                downloaded_entities.append(LocalFile(Path(filename).name))
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
