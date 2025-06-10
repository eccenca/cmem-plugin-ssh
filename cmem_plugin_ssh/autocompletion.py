"""Autocompletion for plugin parameters"""

import stat
from typing import Any, ClassVar

import paramiko
from cmem_plugin_base.dataintegration.context import PluginContext
from cmem_plugin_base.dataintegration.types import Autocompletion, StringParameterType
from paramiko import SSHClient

from cmem_plugin_ssh.utils import load_private_key


def connect_ssh_client(depend_on_parameter_values: list[Any], ssh_client: SSHClient) -> None:
    """Connect to the ssh client with the selected authentication method"""
    if depend_on_parameter_values[5] == "key" or "key_with_password":
        ssh_client.connect(
            hostname=depend_on_parameter_values[0],
            username=depend_on_parameter_values[2],
            pkey=load_private_key(depend_on_parameter_values[3], depend_on_parameter_values[4]),
            port=depend_on_parameter_values[1],
        )
    elif depend_on_parameter_values[5] == "password":
        ssh_client.connect(
            hostname=depend_on_parameter_values[0],
            username=depend_on_parameter_values[2],
            password=depend_on_parameter_values[4],
        )


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
        "authentication_method",
        "path",
    ]

    def autocomplete(
        self,
        query_terms: list[str],
        depend_on_parameter_values: list[Any],
        context: PluginContext,
    ) -> list[Autocompletion]:
        """Autocomplete the folders"""
        _ = context
        result = []
        entered_directory = "".join(query_terms)
        selected_path = depend_on_parameter_values[6]

        # connect to client
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507
        connect_ssh_client(depend_on_parameter_values, ssh_client)

        # open sftp for file getting
        sftp = ssh_client.open_sftp()

        # file getting logic here
        if selected_path == "":
            sftp.chdir(None)
            files_and_folders = sftp.listdir_attr()
            folders = [
                f.filename
                for f in files_and_folders
                if f.st_mode is not None and stat.S_ISDIR(f.st_mode)
            ]
            result = [Autocompletion(value=f, label=f) for f in folders]
            result.append(Autocompletion(value="..", label=".."))
            self.suggestions = result
            sftp.close()
            ssh_client.close()
            return self.suggestions

        if selected_path != "" and entered_directory == "":
            sftp.close()
            ssh_client.close()
            return self.suggestions

        if entered_directory:
            sftp.chdir(entered_directory)
            files_and_folders = sftp.listdir_attr()
            folders = [
                f.filename
                for f in files_and_folders
                if f.st_mode is not None and stat.S_ISDIR(f.st_mode)
            ]
            result = [
                Autocompletion(value=selected_path + "/" + f, label=selected_path + "/" + f)
                for f in folders
            ]
            parent_folder = (
                selected_path[: selected_path.rfind("/")] if "/" in selected_path else ".."
            )
            result.append(Autocompletion(value=parent_folder, label=parent_folder))
            self.suggestions = result
            sftp.close()
            ssh_client.close()
            return self.suggestions

        # close client
        sftp.close()
        ssh_client.close()
        return self.suggestions
