"""Utils for SSH plugins"""

import io
import stat
from collections import OrderedDict

import paramiko
from cmem_plugin_base.dataintegration.parameter.password import Password
from paramiko import RSAKey
from paramiko.sftp_attr import SFTPAttributes
from paramiko.sftp_client import SFTPClient

PASSWORD = "password"  # noqa: S105
PRIVATE_KEY = "key"
AUTHENTICATION_CHOICES = OrderedDict({PASSWORD: "Password", PRIVATE_KEY: "Key"})


def load_private_key(private_key: str | Password, password: str | Password) -> RSAKey | None:
    """Load the private key correctly"""
    if not private_key:
        return None
    pkey = private_key if isinstance(private_key, str) else private_key.decrypt()
    password = password if isinstance(password, str) else password.decrypt()
    pkey = pkey.replace(
        "-----BEGIN OPENSSH PRIVATE KEY-----", "-----BEGIN OPENSSH PRIVATE KEY-----\n"
    )
    pkey = pkey.replace("-----END OPENSSH PRIVATE KEY-----", "\n-----END OPENSSH PRIVATE KEY-----")
    key_file = io.StringIO(pkey)
    if not password:
        return paramiko.RSAKey.from_private_key(key_file)
    return paramiko.RSAKey.from_private_key(key_file, password)


def list_files_parallel(
        sftp: SFTPClient,
        path: str,
        no_subfolders: bool,

) -> list[SFTPAttributes]:
    """List files on ssh instance recursively"""
    all_files = []
    if no_subfolders:
        for entry in sftp.listdir_attr(path):
            if entry.st_mode is not None and not stat.S_ISDIR(entry.st_mode):
                all_files.append(entry)  # noqa: PERF401
        return all_files

    for entry in sftp.listdir_attr(path):
        full_path = f"{path.rstrip('/')}/{entry.filename}"
        if entry.st_mode is not None and stat.S_ISDIR(entry.st_mode):
            all_files.extend(
                list_files_parallel(
                    sftp, full_path, no_subfolders
                )
            )
        else:
            all_files.append(entry)
    return all_files
