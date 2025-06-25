"""Utils for SSH plugins"""

import io
import re
from collections import OrderedDict

from cmem_plugin_base.dataintegration.entity import EntityPath, EntitySchema
from cmem_plugin_base.dataintegration.parameter.password import Password
from paramiko import DSSKey, ECDSAKey, Ed25519Key, PKey, RSAKey, SSHClient, SSHException

from cmem_plugin_ssh.retrieval import SSHRetrieval

PASSWORD = "password"  # noqa: S105
PRIVATE_KEY = "key"
AUTHENTICATION_CHOICES = OrderedDict({PASSWORD: "Password", PRIVATE_KEY: "Key"})

IGNORE = "ignore"
WARNING = "warning"
ERROR = "error"
ERROR_HANDLING_CHOICES = OrderedDict({IGNORE: "Ignore", WARNING: "Warning", ERROR: "Error"})

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


def generate_list_schema() -> EntitySchema:
    """Provide the schema for files"""
    return EntitySchema(
        type_uri="",
        paths=[
            EntityPath(path="file_name"),
            EntityPath(path="size"),
            EntityPath(path="uid"),
            EntityPath(path="gid"),
            EntityPath(path="mode"),
            EntityPath(path="atime"),
            EntityPath(path="mtime"),
        ],
    )


def preview_results(  # noqa: PLR0913
    ssh_client: SSHClient,
    no_subfolder: bool,
    regex: str,
    path: str,
    error_handling: str,
    max_workers: int,
) -> str:
    """Preview the results of an execution"""
    retrieval = SSHRetrieval(
        ssh_client=ssh_client,
        no_subfolder=no_subfolder,
        regex=regex,
    )
    all_files = retrieval.list_files_parallel(
        files=[],
        context=None,
        path=path,
        no_of_max_hits=10,
        error_handling=error_handling,
        workers=max_workers,
        no_access_files=[],
    )
    files = all_files[0]
    no_access_files = all_files[1]

    output = [f"The Following {len(files)} entities were found:", ""]
    output.extend(f"- {file.filename}" for file in files)
    if len(no_access_files) > 0:
        output.append(
            f"\nThe following {len(no_access_files)} entities were found that the current user "
            f"has no access to:"
        )
        output.extend(f"- {no_access_file.filename}" for no_access_file in no_access_files)
    output.append(
        "\n ## Note: \nSince not all files are included in this preview, "
        "the selected error handling method might not always yield accurate results"
    )
    return "\n".join(output)
