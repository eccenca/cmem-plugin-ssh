import io
import re
from collections import OrderedDict

import paramiko
from cmem_plugin_base.dataintegration.parameter.password import Password
from paramiko import RSAKey

PASSWORD = "password"  # noqa: S105
PRIVATE_KEY = "key"
AUTHENTICATION_CHOICES = OrderedDict(
    {
        PASSWORD: "Password",
        PRIVATE_KEY: "Key",
    }
)


def load_private_key(private_key: str | Password) -> RSAKey:
    """Load the private key correctly"""
    pkey = private_key if isinstance(private_key, str) else private_key.decrypt()
    pkey = pkey.replace(
        "-----BEGIN OPENSSH PRIVATE KEY-----", "-----BEGIN OPENSSH PRIVATE KEY-----\n"
    )
    pkey = pkey.replace(
        "-----END OPENSSH PRIVATE KEY-----", "\n-----END OPENSSH PRIVATE KEY-----"
    )
    key_file = io.StringIO(pkey)
    return paramiko.RSAKey.from_private_key(key_file)
