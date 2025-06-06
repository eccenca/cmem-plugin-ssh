from typing import Any, ClassVar

import paramiko
from cmem_plugin_base.dataintegration.context import PluginContext
from cmem_plugin_base.dataintegration.types import Autocompletion, StringParameterType

from cmem_plugin_ssh.utils import load_private_key


class DirectoryParameterType(StringParameterType):
    """Autocomplete class for folders on the ssh instance"""

    def __init__(
        self,
        url_expand: str,
        display_name: str,
    ) -> None:
        self.url_expand = url_expand
        self.display_name = display_name
        self.suggestions: list[Autocompletion] = []

    autocompletion_depends_on_parameters: ClassVar[list[str]] = [
        "hostname",
        "port",
        "username",
        "private_key",
        "password",
    ]

    def autocomplete(
        self,
        query_terms: list[str],
        depend_on_parameter_values: list[Any],
        context: PluginContext,
    ) -> list[Autocompletion]:
        """Autocomplete the folders"""
        _ = context
        _ = query_terms
        result = []
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507
        ssh_client.connect(
            hostname=depend_on_parameter_values[0],
            username=depend_on_parameter_values[2],
            pkey=load_private_key(depend_on_parameter_values[3], depend_on_parameter_values[4]),
            port=depend_on_parameter_values[1],
        )
        sftp = ssh_client.open_sftp()
        files_and_folders = sftp.listdir()
        result = [Autocompletion(value=f, label=f) for f in files_and_folders]
        self.suggestions = result
        return self.suggestions
