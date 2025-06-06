"""SSH List files task plugin"""

from collections.abc import Sequence

import paramiko
from cmem_plugin_base.dataintegration.context import ExecutionContext
from cmem_plugin_base.dataintegration.description import Plugin, PluginParameter
from cmem_plugin_base.dataintegration.entity import Entities
from cmem_plugin_base.dataintegration.parameter.choice import ChoiceParameterType
from cmem_plugin_base.dataintegration.parameter.password import Password, PasswordParameterType
from cmem_plugin_base.dataintegration.plugins import WorkflowPlugin
from paramiko import RSAKey

from cmem_plugin_ssh.autocompletion import DirectoryParameterType
from cmem_plugin_ssh.utils import AUTHENTICATION_CHOICES, load_private_key


@Plugin(
    label="List SSH files",
    plugin_id="cmem_plugin_ssh-List",
    description="SSH list files",
    documentation="""
    """,
    parameters=[
        PluginParameter(name="hostname", label="Hostname", description="Hostname to connect to."),
        PluginParameter(name="port", default_value=22),
        PluginParameter(
            name="username",
        ),
        PluginParameter(
            name="authentication_method", param_type=ChoiceParameterType(AUTHENTICATION_CHOICES)
        ),
        PluginParameter(
            name="private_key",
            param_type=PasswordParameterType(),
        ),
        PluginParameter(name="password", param_type=PasswordParameterType(), default_value=""),
        PluginParameter(
            name="path",
            default_value="",
            param_type=DirectoryParameterType("directories", "Folder"),
        ),
    ],
)
class ListFiles(WorkflowPlugin):
    """List Plugin SSH"""

    def __init__(  # noqa: PLR0913
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
        self.private_key = load_private_key(private_key)
        self.password = password if isinstance(password, str) else password.decrypt()
        self.path = path

        self.ssh_client = paramiko.SSHClient()
        self.connect_ssh_client(
            self.hostname, self.username, self.private_key, self.port, self.password
        )

        self.sftp = self.ssh_client.open_sftp()

    def close_connections(self) -> None:
        """Close connection from sftp and ssh"""
        self.sftp.close()
        self.ssh_client.close()

    def connect_ssh_client(
        self, hostname: str, username: str, private_key: RSAKey, port: int, password: str | Password
    ) -> None:
        """Connect to the ssh client with the selected authentication method"""
        _ = password
        if self.authentication_method == "key":
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                hostname=hostname,
                username=username,
                pkey=private_key,
                port=port,
            )

    def execute(self, inputs: Sequence[Entities], context: ExecutionContext) -> Entities | None:
        """Execute the workflow task"""
        _ = inputs
        _ = context
        return None
