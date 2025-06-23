"""Autocompletion for plugin parameters"""

import stat
from typing import Any, ClassVar

import paramiko
from cmem_plugin_base.dataintegration.context import PluginContext
from cmem_plugin_base.dataintegration.types import Autocompletion, StringParameterType
from paramiko import SFTPAttributes, SFTPClient, SSHClient

from cmem_plugin_ssh.utils import load_private_key


def sort_suggestions(suggestions: list[Autocompletion], query_terms: list[str]) -> None:
    """Sort autocompleted suggestions"""
    suggestions.sort(
        key=lambda x: (
            not all(term.lower() in x.label.lower() for term in query_terms),
            x.label.lower(),
        )
    )


def connect_ssh_client(depend_on_parameter_values: list[Any], ssh_client: SSHClient) -> None:
    """Connect to the ssh client with the selected authentication method"""
    if depend_on_parameter_values[5] == "key":
        pw = (
            depend_on_parameter_values[4]
            if isinstance(depend_on_parameter_values[4], str)
            else depend_on_parameter_values[4].decrypt()
        )
        ssh_client.connect(
            hostname=depend_on_parameter_values[0],
            username=depend_on_parameter_values[2],
            pkey=load_private_key(depend_on_parameter_values[3], depend_on_parameter_values[4]),
            password=pw,
            port=depend_on_parameter_values[1],
            timeout=20,
        )
    elif depend_on_parameter_values[5] == "password":
        pw = (
            depend_on_parameter_values[4]
            if isinstance(depend_on_parameter_values[4], str)
            else depend_on_parameter_values[4].decrypt()
        )
        ssh_client.connect(
            hostname=depend_on_parameter_values[0],
            username=depend_on_parameter_values[2],
            password=pw,
            port=depend_on_parameter_values[1],
            timeout=20,
        )


def close_connection(sftp: SFTPClient, ssh_client: SSHClient) -> None:
    """Close SFTP and SSH session connection"""
    sftp.close()
    ssh_client.close()


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

        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507
        connect_ssh_client(depend_on_parameter_values, ssh_client)

        sftp = ssh_client.open_sftp()

        if selected_path == "":
            sftp.chdir(None)
            files_and_folders = self.list_folders(sftp)
            folders = [
                f.filename
                for f in files_and_folders
                if f.st_mode is not None and stat.S_ISDIR(f.st_mode)
            ]
            current_dir = sftp.normalize(".")
            result = [
                Autocompletion(
                    value=current_dir + "/" + f if current_dir != "/" else "/" + f,
                    label=current_dir + "/" + f if current_dir != "/" else "/" + f,
                )
                for f in folders
            ]
            sort_suggestions(result, query_terms)
            result.append(Autocompletion(value=current_dir, label=current_dir))
            parent_dir = (
                current_dir.rsplit("/", 1)[0] or "/" if not current_dir.endswith("/") else "/"
            )
            result.append(Autocompletion(value=parent_dir, label=parent_dir))
            self.suggestions = result
            close_connection(sftp, ssh_client)
            return self.suggestions

        if selected_path != "" and entered_directory == "":
            close_connection(sftp, ssh_client)
            return self.suggestions

        if entered_directory:
            sftp.chdir(entered_directory)
            files_and_folders = self.list_folders(sftp)
            folders = [
                f.filename
                for f in files_and_folders
                if f.st_mode is not None and stat.S_ISDIR(f.st_mode)
            ]
            current_dir = sftp.normalize(".")
            result = [
                Autocompletion(
                    value=current_dir + "/" + f if current_dir != "/" else "/" + f,
                    label=current_dir + "/" + f if current_dir != "/" else "/" + f,
                )
                for f in folders
            ]
            sort_suggestions(result, query_terms)
            result.append(Autocompletion(value=current_dir, label=current_dir))
            parent_dir = (
                current_dir.rsplit("/", 1)[0] or "/" if not current_dir.endswith("/") else "/"
            )
            if sftp.getcwd() != "/":
                result.append(Autocompletion(value=parent_dir, label=parent_dir))
            self.suggestions = result
            close_connection(sftp, ssh_client)
            return self.suggestions

        return self.suggestions

    def list_folders(self, sftp: SFTPClient) -> list[SFTPAttributes]:
        """List folders from given SFTP client"""
        try:
            files_and_folders = sftp.listdir_attr()
        except (paramiko.ChannelException, OSError, paramiko.SFTPError) as e:
            current_dir = sftp.normalize(".")
            parent_dir = (
                current_dir.rsplit("/", 1)[0] or "/" if not current_dir.endswith("/") else "/"
            )
            self.suggestions = [Autocompletion(value=parent_dir, label=parent_dir)]
            raise ValueError(f"Unable to list folder items at '{current_dir or '.'}': {e}") from e
        return files_and_folders
