"""Utils for SSH plugins"""

import io
import re
from collections import OrderedDict

from cmem_plugin_base.dataintegration.parameter.password import Password
from paramiko import DSSKey, ECDSAKey, Ed25519Key, PKey, RSAKey, SSHException

PASSWORD = "password"  # noqa: S105
PRIVATE_KEY = "key"
AUTHENTICATION_CHOICES = OrderedDict({PASSWORD: "Password", PRIVATE_KEY: "Key"})

MAX_WORKERS = 32


def load_private_key(private_key: str | Password, password: str | Password) -> PKey | None:
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
    loaders: list[type[PKey]] = [RSAKey, DSSKey, ECDSAKey, Ed25519Key]
    for loader in loaders:
        try:
            if password:
                return loader.from_private_key(key_file, password=password)
            return loader.from_private_key(key_file)
        except SSHException:
            key_file.seek(0)  # Reset file pointer for next try
            continue
    return None


def setup_max_workers(max_workers: int) -> int:
    """Return the correct number of workers"""
    if 0 < max_workers <= MAX_WORKERS:
        return max_workers
    raise ValueError("Range of max_workers exceeded")
