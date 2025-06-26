"""Execute command task workflow plugin"""

from collections.abc import Sequence

import paramiko
from cmem_plugin_base.dataintegration.context import ExecutionContext
from cmem_plugin_base.dataintegration.description import Icon, Plugin, PluginParameter
from cmem_plugin_base.dataintegration.entity import Entities, Entity, EntityPath, EntitySchema
from cmem_plugin_base.dataintegration.parameter.choice import ChoiceParameterType
from cmem_plugin_base.dataintegration.parameter.password import Password, PasswordParameterType
from cmem_plugin_base.dataintegration.plugins import WorkflowPlugin
from cmem_plugin_base.dataintegration.ports import FixedNumberOfInputs, FixedSchemaPort
from cmem_plugin_base.dataintegration.typed_entities.file import FileEntitySchema

from cmem_plugin_ssh.autocompletion import DirectoryParameterType
from cmem_plugin_ssh.utils import AUTHENTICATION_CHOICES, load_private_key


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


@Plugin(
    label="Execute commands via SSH",
    plugin_id="cmem_plugin_ssh-Execute",
    description="Execute commands on a given SSH instance.",
    documentation="""
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
            name="command",
            label="Command",
            description="The command that will be executed on the SSH instance.",
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
        self.command = command
        self.timeout = timeout
        self.input_ports = FixedNumberOfInputs([FixedSchemaPort(schema=FileEntitySchema())])
        self.output_port = FixedSchemaPort(schema=generate_schema())
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

    def execute(self, inputs: Sequence[Entities], context: ExecutionContext) -> Entities | None:
        """Execute the workflow task"""
        input_data = None

        files = inputs[0].entities
        for file in files:
            stdin_file = FileEntitySchema().from_entity(file)
            with stdin_file.read_stream(context.task.project_id()) as stdin:
                input_data = stdin.read()

        stdin, stdout, stderr = self.ssh_client.exec_command(self.command)
        stdin.write(input_data)
        stdin.channel.shutdown_write()

        output = stdout.read().decode("utf-8")
        error = stderr.read().decode("utf-8")
        exit_code = stdout.channel.recv_exit_status()
        self.close_connections()

        entity = Entity(uri=f"{self.hostname}", values=[[str(exit_code)], [output], [error]])

        return Entities(entities=iter([entity]), schema=generate_schema())
