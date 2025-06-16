"""Utils for SSH plugins"""

import io
import re
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
    match = re.search(
        r"(-----BEGIN (.+?) PRIVATE KEY-----)(.*?)(-----END (.+?) PRIVATE KEY-----)",
        pkey,
        re.DOTALL,
    )
    if not match:
        raise ValueError("Unsupported private key format")

    begin, body, end = match.group(1), match.group(3).strip(), match.group(4)
    pkey = f"{begin}\n{body}\n{end}"

    key_file = io.StringIO(pkey)
    if not password:
        return paramiko.RSAKey.from_private_key(key_file)
    return paramiko.RSAKey.from_private_key(key_file, password)
