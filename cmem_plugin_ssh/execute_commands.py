"""Execute command task workflow plugin"""

import tempfile
from collections.abc import Sequence
from pathlib import Path

import paramiko
from cmem_plugin_base.dataintegration.context import ExecutionContext, ExecutionReport
from cmem_plugin_base.dataintegration.description import Icon, Plugin, PluginParameter
from cmem_plugin_base.dataintegration.entity import Entities, Entity, EntityPath, EntitySchema
from cmem_plugin_base.dataintegration.parameter.choice import ChoiceParameterType
from cmem_plugin_base.dataintegration.parameter.password import Password, PasswordParameterType
from cmem_plugin_base.dataintegration.plugins import WorkflowPlugin
from cmem_plugin_base.dataintegration.ports import FixedNumberOfInputs, FixedSchemaPort, Port
from cmem_plugin_base.dataintegration.typed_entities.file import FileEntitySchema, LocalFile

from cmem_plugin_ssh.autocompletion import DirectoryParameterType
from cmem_plugin_ssh.utils import (
    AUTHENTICATION_CHOICES,
    COMMAND_INPUT_CHOICES,
    COMMAND_OUTPUT_CHOICES,
    FILE_INPUT,
    FILE_OUTPUT,
    NO_INPUT,
    NO_OUTPUT,
    STRUCTURED_OUPUT,
    load_private_key,
)


def generate_schema() -> EntitySchema:
    """Generate the schema for entities"""
    return EntitySchema(
        type_uri="",
        paths=[
            EntityPath(path="exit_code"),
            EntityPath(path="std_out"),
            EntityPath(path="std_err"),
        ],
    )


def setup_timeout(timeout: float) -> float | None:
    """Configure correct timeout"""
    if timeout < 0:
        raise ValueError("Negative value not allowed for timeout!")
    if timeout == 0:
        return None
    return timeout


@Plugin(
    label="Execute commands via SSH",
    plugin_id="cmem_plugin_ssh-Execute",
    description="Execute a command on an SSH server.",
    documentation="""
Runs a command on an SSH server and collects what it produces.

The input and output methods decide the shape of the task. With file input, an input
port accepts file entities and the command runs once per incoming file, with the
content of that file on its standard input; without it, the command runs exactly once.
What leaves the task is either one entity per run, carrying the exit code, the standard
output and the standard error, or one file per run holding the raw standard output, or
nothing at all, in which case the task ends the branch of the workflow it sits in.

**Upload SSH files** and **Download SSH files** move the files a command works on, so a
common chain is to upload files, run a command over them and download the result.

#### Caveats

* The exit code is never inspected. A failing command leaves the task successful and
the workflow running, and the failure shows up only in the emitted exit code and
standard error. With file output, both are dropped and the standard output is kept
alone.
* The command is sent as it is written and interpreted by the login shell of the
account, without any escaping or checking, and it runs with every right that account
has.
* The command runs in whatever directory the account lands in on login. The configured
directory is not entered.
* With file input, each incoming file is read into memory as a whole before it is sent.
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
                "Remote directory, kept with the task but not entered before the command runs."
                " Autocompletion starts in the home directory of the account, use '..' for the"
                " parent directory or '/' for the root directory."
            ),
            default_value="",
            param_type=DirectoryParameterType("directories", "Folder"),
        ),
        PluginParameter(
            name="input_method",
            label="Input method",
            description="Whether incoming files are fed to the command, which also decides "
            "whether the task has an input port.",
            param_type=ChoiceParameterType(COMMAND_INPUT_CHOICES),
        ),
        PluginParameter(
            name="output_method",
            label="Output method",
            description="What the task emits for each run of the command, which also decides "
            "whether the task has an output port.",
            param_type=ChoiceParameterType(COMMAND_OUTPUT_CHOICES),
        ),
        PluginParameter(
            name="command",
            label="Command",
            description="Command line executed on the server.",
            default_value="ls",
        ),
        PluginParameter(
            name="timeout",
            label="Timeout",
            description="Seconds the task waits for the command to send data before it gives up "
            "and fails. Zero waits for as long as the command takes.",
            default_value=0,
        ),
    ],
)
class ExecuteCommands(WorkflowPlugin):
    """Execute commands Plugin SSH"""

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
        input_method: str,
        output_method: str,
        command: str,
        timeout: int,
    ):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.authentication_method = authentication_method
        self.private_key = private_key
        self.password = password if isinstance(password, str) else password.decrypt()
        self.path = path
        self.input_method = input_method
        self.output_method = output_method
        self.command = command
        self.timeout = setup_timeout(timeout)
        self.input_ports = self.setup_input_port()
        self.output_port = self.setup_output_port()

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
        entities: list = []

        self._initialize_ssh_and_sftp_connections()
        context.report.update(
            ExecutionReport(
                entity_count=len(entities),
                operation="execute",
                operation_desc=f"executing '{self.command}'",
            )
        )
        if self.input_method == "file_input":
            self.input_execution(context, entities, inputs)

        if self.input_method == "no_input":
            self.no_input_execution(entities)

        self.cleanup_ssh_connections()

        operation_desc = (
            f"times executed '{self.command}'"
            if len(entities) > 1
            else f"executed '{self.command}'"
        )

        schema = FileEntitySchema() if self.output_method == FILE_OUTPUT else generate_schema()

        context.report.update(
            ExecutionReport(
                entity_count=len(entities),
                operation="done",
                operation_desc=operation_desc,
                sample_entities=Entities(entities=iter(entities[:10]), schema=schema),
            )
        )

        return Entities(entities=iter(entities), schema=schema)

    def input_execution(
        self, context: ExecutionContext, entities: list, inputs: Sequence[Entities]
    ) -> None:
        """Execute the command with given input files"""
        files = inputs[0].entities
        for file in files:
            stdin_file = FileEntitySchema().from_entity(file)
            context.report.update(
                ExecutionReport(
                    entity_count=len(entities),
                    operation="execute",
                    operation_desc=f"executing '{self.command}' with {stdin_file.path}",
                )
            )
            with stdin_file.read_stream(context.task.project_id()) as stdin:
                input_data = stdin.read()

            stdin, stdout, stderr = self.ssh_client.exec_command(self.command, timeout=self.timeout)
            stdin.write(input_data)
            stdin.channel.shutdown_write()
            exit_code = stdout.channel.recv_exit_status()

            if self.output_method in (STRUCTURED_OUPUT, NO_OUTPUT):
                output = stdout.read().decode("utf-8")
                error = stderr.read().decode("utf-8")
                entity = Entity(
                    uri=f"{self.hostname}", values=[[str(exit_code)], [output], [error]]
                )
                entities.append(entity)

            if self.output_method == FILE_OUTPUT:
                output_bytes = stdout.read()
                tmp_dir = tempfile.mkdtemp()
                input_filename = Path(stdin_file.path).name
                tmp_path = Path(tmp_dir) / f"{input_filename}_stdout.bin"
                with Path.open(tmp_path, "wb") as f:
                    f.write(output_bytes)
                local_file = LocalFile(path=str(tmp_path))
                entity = FileEntitySchema().to_entity(value=local_file)
                entities.append(entity)

    def no_input_execution(self, entities: list) -> None:
        """Execute the command with no given input files"""
        _, stdout, stderr = self.ssh_client.exec_command(
            self.command,
            timeout=self.timeout,
        )
        if self.output_method in (STRUCTURED_OUPUT, NO_OUTPUT):
            output = stdout.read().decode("utf-8")
            error = stderr.read().decode("utf-8")
            exit_code = stdout.channel.recv_exit_status()
            entity = Entity(uri=f"{self.hostname}", values=[[str(exit_code)], [output], [error]])
            entities.append(entity)
        if self.output_method == FILE_OUTPUT:
            output_bytes = stdout.read()
            tmp_dir = tempfile.mkdtemp()
            tmp_path = Path(tmp_dir) / "stdout.bin"
            with Path.open(tmp_path, "wb") as f:
                f.write(output_bytes)

            local_file = LocalFile(path=str(tmp_path))
            entity = FileEntitySchema().to_entity(value=local_file)
            entities.append(entity)

    def setup_input_port(self) -> FixedNumberOfInputs:
        """Set up the input port depending on the set input method"""
        if self.input_method == NO_INPUT:
            return FixedNumberOfInputs([])
        if self.input_method == FILE_INPUT:
            return FixedNumberOfInputs([FixedSchemaPort(schema=FileEntitySchema())])
        raise ValueError("Could not set up input port. Invalid input method!")

    def setup_output_port(self) -> Port | None:
        """Set up the output port depending on the set output method"""
        if self.output_method == NO_OUTPUT:
            return None
        if self.output_method == STRUCTURED_OUPUT:
            return FixedSchemaPort(schema=generate_schema())
        if self.output_method == FILE_OUTPUT:
            return FixedSchemaPort(schema=FileEntitySchema())
        raise ValueError("Could not set up output port. Invalid output method!")
