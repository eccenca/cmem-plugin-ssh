import io
import re
from collections import OrderedDict

import paramiko
from cmem_plugin_base.dataintegration.parameter.password import Password
from paramiko import RSAKey

PASSWORD = "password"
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
    pkey = re.sub(r"(-----BEGIN [A-Z ]+ KEY-----)(?!\n)", r"\1\n", pkey)
    pkey = re.sub(r"(-----END [A-Z ]+ KEY-----)(?!\n)", r"\n\1", pkey)
    key_file = io.StringIO(pkey)
    return paramiko.RSAKey.from_private_key(key_file)
