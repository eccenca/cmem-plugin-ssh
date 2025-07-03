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


def setup_timeout(timeout: float) -> None | float:
    """Configure correct timeout"""
    if timeout < 0:
        raise ValueError("Negative value not allowed for timeout!")
    if timeout == 0:
        return None
    return timeout


@Plugin(
    label="Execute commands via SSH",
    plugin_id="cmem_plugin_ssh-Execute",
    description="Execute commands on a given SSH instance.",
    documentation="""
This workflow task executes commands on a given SSH instance.

By providing the hostname, username, port and authentication method, you can specify the
folder in which the command should be executed in.

#### Input Methods:
* **No input:** The command will be executed with no input attached to the plugin. Stdin
is non-existent in this case.
* **File input:** The command will be executed with the stdin being represented by the
files that are connected via the input port of the plugin. This also allows for looping
over multiple files executing the same command over them.


#### Output Methods:
* **Structured process output:** The output will produce entities with its own schema including
the stdout and stderr as well as the exit code to confirm the execution of the command.
* **File output:** The stdout will be converted into a file a be provided for further use.
* **No output:** The output port will be closed.

#### Authentication Methods:
* **Password:** Only the password will be used for authentication. The private key field is
ignored, even if filled.
* **Key:** The private key will be used for authentication. If the key is encrypted, the password
will be used to decrypt it.

#### Note:
* If a connection cannot be established within 20 seconds, a timeout occurs.
* Currently supported key types are: RSA, DSS, ECDSA, Ed25519.
    """,
    icon=Icon(package=__package__, file_name="ssh-icon.svg"),
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
            name="input_method",
            label="Input method",
            description="Parameter to decide weather files will be used as stdin or no input is "
            "needed. If 'File input' is chosen, the input port will open for all entities with"
            "the FileEntitySchema.",
            param_type=ChoiceParameterType(COMMAND_INPUT_CHOICES),
        ),
        PluginParameter(
            name="output_method",
            label="Output method",
            description="Parameter to decide which type of output the user wants. This can be "
            "either no output, a structured process output with its own schema or "
            "a file based output",
            param_type=ChoiceParameterType(COMMAND_OUTPUT_CHOICES),
        ),
        PluginParameter(
            name="command",
            label="Command",
            description="The command that will be executed on the SSH instance. When the input"
            "method is set to 'File input', the command will be executed over these files.",
            default_value="ls",
        ),
        PluginParameter(
            name="timeout",
            label="Timeout",
            description="A timeout for the executed command.",
            default_value=0,
        ),
    ],
)
class ExecuteCommands(WorkflowPlugin):
    """Execute commands Plugin SSH"""

    def __init__(  # noqa: PLR0913
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

    def execute(self, inputs: Sequence[Entities], context: ExecutionContext) -> Entities:
        """Execute the workflow task"""
        entities: list = []
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

        self.close_connections()

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
        stdin, stdout, stderr = self.ssh_client.exec_command(
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
