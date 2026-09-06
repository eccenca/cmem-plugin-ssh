"""Upload SSH files workflow task"""

import gzip
import io
from collections.abc import Sequence
from pathlib import Path

import paramiko
from cmem_plugin_base.dataintegration.context import ExecutionContext, ExecutionReport
from cmem_plugin_base.dataintegration.description import Icon, Plugin, PluginParameter
from cmem_plugin_base.dataintegration.entity import Entities
from cmem_plugin_base.dataintegration.parameter.choice import ChoiceParameterType
from cmem_plugin_base.dataintegration.parameter.password import Password, PasswordParameterType
from cmem_plugin_base.dataintegration.plugins import WorkflowPlugin
from cmem_plugin_base.dataintegration.ports import FixedNumberOfInputs, FixedSchemaPort
from cmem_plugin_base.dataintegration.typed_entities.file import File, FileEntitySchema

from cmem_plugin_ssh.autocompletion import DirectoryParameterType
from cmem_plugin_ssh.utils import AUTHENTICATION_CHOICES, load_private_key


def _is_gzip(stream: io.BufferedReader) -> bool:
    head = stream.read(2)
    stream.seek(0)
    return head == b"\x1f\x8b"


@Plugin(
    label="Upload SSH files",
    plugin_id="cmem_plugin_ssh-Upload",
    description="Upload files to an SSH server.",
    documentation="""
Uploads the files it receives to a directory on an SSH server.

Files arrive on the input port as file entities and are written into the configured
directory under their plain file name. The task has no output port: it ends the branch
of the workflow it sits in and hands nothing on to a following task.

**Download SSH files** covers the other direction, and **Execute commands via SSH**
runs a command on the uploaded files once they are in place.

#### Caveats

* Content that is gzip compressed is unpacked before it is sent. Such a file arrives on
the server uncompressed, under an unchanged name that still ends in `.gz`.
* A file of the same name already on the server is overwritten without warning, and so
are files of the same name coming from different folders.
* The first failing upload aborts the task. Files uploaded before that stay on the
server, and nothing is rolled back.
* The target directory has to exist. It is not created.
* The task logs in with the configured credentials only, and offers no key of the
machine it runs on. The host key of the server in turn is accepted as presented and
never checked against a known hosts list.
* Establishing the connection fails after 20 seconds.
    """,
    icon=Icon(package=__package__, file_name="ssh-icon.svg"),
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
                "Remote directory the files are written to. Autocompletion starts in the home"
                " directory of the account, use '..' for the parent directory"
                " or '/' for the root directory."
            ),
            default_value="",
            param_type=DirectoryParameterType("directories", "Folder"),
        ),
    ],
)
class UploadFiles(WorkflowPlugin):
    """Upload Plugin SSH"""

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
    ):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.authentication_method = authentication_method
        self.private_key = private_key
        self.password = password if isinstance(password, str) else password.decrypt()
        self.path = path
        self.input_ports = FixedNumberOfInputs([FixedSchemaPort(schema=FileEntitySchema())])
        self.output_port = None

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

    def execute(self, inputs: Sequence[Entities], context: ExecutionContext) -> Entities:
        """Execute the workflow task"""
        _ = inputs
        _ = context
        if len(inputs) == 0:
            raise ValueError("No input was given!")

        self._initialize_ssh_and_sftp_connections()

        files: list = []
        schema = FileEntitySchema()

        for entity in inputs[0].entities:
            file = schema.from_entity(entity)
            file_name = Path(file.path).name
            context.report.update(
                ExecutionReport(
                    entity_count=len(files),
                    operation="upload",
                    operation_desc=f"uploading {file_name}",
                )
            )
            with file.read_stream(context=context) as input_file:
                # Wrap input in buffered stream if needed
                buffered = io.BufferedReader(input_file)

                # Check if Gzip by peeking at first two bytes
                if _is_gzip(buffered):
                    decompressed_stream = gzip.GzipFile(fileobj=buffered)
                else:
                    decompressed_stream = buffered  # type: ignore[assignment]

                # Decide whether it's text or binary (peek and try decode)
                sample = decompressed_stream.read(1024)
                decompressed_stream.seek(0)

                try:
                    sample.decode("utf-8")
                    is_text = True
                except UnicodeDecodeError:
                    is_text = False

                if is_text:
                    stream_for_upload = io.TextIOWrapper(decompressed_stream, encoding="utf-8")
                else:
                    stream_for_upload = decompressed_stream  # type: ignore[assignment]

                try:
                    # Stream directly to SFTP — no full buffering
                    self.sftp.putfo(stream_for_upload, f"{self.path}/{file_name}")  # type: ignore[arg-type]
                except (FileNotFoundError, PermissionError, OSError) as e:
                    raise ValueError(f"An error occurred during upload: {e}") from e

            files.append(
                File(
                    path=file.path,
                    entry_path=file.entry_path,
                    mime=file.mime,
                    file_type=file.file_type,
                )
            )

        entities = [schema.to_entity(file) for file in files]

        context.report.update(
            ExecutionReport(
                entity_count=len(entities),
                operation="write",
                operation_desc="files uploaded",
                sample_entities=Entities(entities=iter(entities[:10]), schema=schema),
            )
        )
        self.cleanup_ssh_connections()
        return Entities(entities=iter(entities), schema=schema)
