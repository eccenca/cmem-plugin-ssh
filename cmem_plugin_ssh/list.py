"""SSH List files task plugin"""

from collections.abc import Sequence

import paramiko
from cmem_plugin_base.dataintegration.context import ExecutionContext, ExecutionReport
from cmem_plugin_base.dataintegration.description import Icon, Plugin, PluginAction, PluginParameter
from cmem_plugin_base.dataintegration.entity import Entities, Entity
from cmem_plugin_base.dataintegration.parameter.choice import ChoiceParameterType
from cmem_plugin_base.dataintegration.parameter.password import Password, PasswordParameterType
from cmem_plugin_base.dataintegration.plugins import WorkflowPlugin
from cmem_plugin_base.dataintegration.ports import FixedNumberOfInputs, FixedSchemaPort

from cmem_plugin_ssh.autocompletion import DirectoryParameterType
from cmem_plugin_ssh.retrieval import SSHRetrieval
from cmem_plugin_ssh.utils import (
    AUTHENTICATION_CHOICES,
    ERROR_HANDLING_CHOICES,
    generate_list_schema,
    load_private_key,
    preview_results,
    setup_max_workers,
)


@Plugin(
    label="List SSH files",
    plugin_id="cmem_plugin_ssh-List",
    description="List the files of a directory on an SSH server, with their metadata.",
    documentation="""
Lists the files of a directory on an SSH server, together with the metadata the
server reports for them.

The task takes no input. It emits one entity per file, holding the full remote path
in `file_name`, plus `size`, `uid`, `gid`, `mode`, `atime` and `mtime` exactly as the
server reports them: a byte count, numeric owner and group ids, numeric mode bits and
Unix timestamps. Folders are traversed but never emitted.

**Download SSH files** accepts these entities on its input port, so that listing and
downloading can be split into two steps, with transformations in between that narrow
down which of the listed files are fetched.

The **Preview results** action lists the first ten matches without running the
workflow. It stops after ten files, so it can miss the unreadable file that would make
a real run behave differently.

#### Caveats

* Files the account cannot read are listed like every other file. The error handling
only decides whether they are reported on top of that, or the listing fails.
* A folder that cannot be read is skipped silently unless the error handling is set to
Error, and the files below it are then missing from the result without further notice.
* Every file is opened and one byte is read from it to find out whether it is readable,
which makes listing a large directory noticeably slower than a plain directory listing.
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
        )
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
                "Remote directory the task works in. Autocompletion starts in the home"
                " directory of the account, use '..' for the parent directory"
                " or '/' for the root directory."
            ),
            default_value="",
            param_type=DirectoryParameterType("directories", "Folder"),
        ),
        PluginParameter(
            name="regex",
            label="Regular expression",
            description="Regular expression a file name has to match completely to be listed. "
            "It is matched against the plain file name, not against the path.",
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
            description="If enabled, only the given directory is listed and its subfolders are "
            "left out.",
            default_value=False,
        ),
        PluginParameter(
            name="max_workers",
            label="Maximum number of workers",
            description="Number of threads that list subfolders in parallel, from 1 to 32. More "
            "threads speed up a deep folder tree, but too many parallel channels make some "
            "servers refuse them with a ChannelException.",
            default_value=1,
            advanced=True,
        ),
    ],
)
class ListFiles(WorkflowPlugin):
    """List Plugin SSH"""

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
        self.input_ports = FixedNumberOfInputs([])
        self.output_port = FixedSchemaPort(schema=generate_list_schema())

    def cleanup_ssh_connections(self) -> None:
        """Close connection from sftp and ssh"""
        self.sftp.close()
        self.ssh_client.close()

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

    def _initialize_ssh_and_sftp_connections(self) -> None:
        self.ssh_client = paramiko.SSHClient()
        self.establish_ssh_connection()
        self.sftp = self.ssh_client.open_sftp()

    def execute(self, inputs: Sequence[Entities], context: ExecutionContext) -> Entities:
        """Execute the workflow task"""
        _ = inputs
        context.report.update(
            ExecutionReport(entity_count=0, operation="wait", operation_desc="files listed.")
        )
        entities = []

        self._initialize_ssh_and_sftp_connections()

        retrieval = SSHRetrieval(
            ssh_client=self.ssh_client,
            no_subfolder=self.no_subfolder,
            regex=self.regex,
        )
        all_files = retrieval.list_files_parallel(
            files=[],
            context=context,
            path=self.path,
            workers=self.max_workers,
            error_handling=self.error_handling,
            no_access_files=[],
        )
        files = all_files[0]
        context.report.update(
            ExecutionReport(
                entity_count=len(files), operation="wait", operation_desc="files listed."
            )
        )

        for file in files:
            entities.append(
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
                    operation="write",
                    operation_desc="entities generated",
                )
            )

        if self.error_handling == "warning" and len(all_files[1]) > 0:
            faulty_files = all_files[1]
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
                    sample_entities=Entities(
                        entities=iter(entities[:10]), schema=generate_list_schema()
                    ),
                )
            )

        self.cleanup_ssh_connections()

        return Entities(
            entities=iter(entities),
            schema=generate_list_schema(),
        )
