"""Utils for SSH plugins"""

import io
from collections import OrderedDict

import paramiko
from cmem_plugin_base.dataintegration.parameter.password import Password
from paramiko import RSAKey

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
