"""Pytest configuration"""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from cmem_plugin_ssh.download import DownloadFiles
from cmem_plugin_ssh.list import ListFiles
from tests.fixtures import (
    SSH_HOSTNAME,
    SSH_PASSWORD,
    SSH_PORT,
    SSH_PRIVATE_KEY,
    SSH_PRIVATE_KEY_WITH_PASSWORD,
    SSH_USERNAME,
)


@dataclass
class TestingEnvironment:
    """Testing Environment"""

    __test__ = False

    hostname: str
    port: int
    username: str
    authentication_method: str
    private_key: str
    private_key_with_password: str
    password: str
    error_handling: str
    path: str
    regex: str
    no_subfolder: bool
    restricted_file: str
    list_plugin: ListFiles
    download_plugin: DownloadFiles
    no_of_files: int = 12


@pytest.fixture
def testing_environment() -> TestingEnvironment:
    """Provide testing environment"""
    hostname = SSH_HOSTNAME
    port = SSH_PORT
    username = SSH_USERNAME
    authentication_method = "key"
    private_key = SSH_PRIVATE_KEY
    private_key_with_password = SSH_PRIVATE_KEY_WITH_PASSWORD
    password = SSH_PASSWORD
    error_handling = "error"
    path = "volume"
    regex = "^.*$"
    restricted_file = "restricted.txt"
    no_subfolder = False
    list_plugin = ListFiles(
        hostname=hostname,
        port=port,
        username=username,
        private_key=private_key,
        path=path,
        regex=regex,
        password=password,
        authentication_method=authentication_method,
        no_subfolder=no_subfolder,
        error_handling=error_handling,
    )
    download_plugin = DownloadFiles(
        hostname=hostname,
        port=port,
        username=username,
        private_key=private_key,
        path=path,
        regex=regex,
        password=password,
        authentication_method=authentication_method,
        no_subfolder=no_subfolder,
        error_handling=error_handling,
    )

    return TestingEnvironment(
        hostname=hostname,
        port=port,
        username=username,
        authentication_method=authentication_method,
        private_key=private_key,
        private_key_with_password=private_key_with_password,
        password=password,
        path=path,
        no_subfolder=no_subfolder,
        regex=regex,
        error_handling=error_handling,
        restricted_file=restricted_file,
        list_plugin=list_plugin,
        download_plugin=download_plugin,
    )


def get_compose_cmd() -> list[str]:
    """Get the correct compose command for environment"""
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return ["docker", "compose"]


DOCKER_COMPOSE_DIR = Path(__file__).parent.parent / "docker"
DOCKER_COMPOSE_FILE = "docker-compose.yml"


@pytest.fixture(scope="session", autouse=True)
def ssh_test_container():  # noqa: ANN201
    """Start the SSH test container before tests and stop it after."""
    subprocess.run(  # noqa: S603
        [*get_compose_cmd(), "-f", DOCKER_COMPOSE_FILE, "up", "--build", "-d"],
        cwd=DOCKER_COMPOSE_DIR,
        check=True,
    )
    yield
    subprocess.run(  # noqa: S603
        [*get_compose_cmd(), "-f", DOCKER_COMPOSE_FILE, "down", "--rmi", "all"],
        cwd=DOCKER_COMPOSE_DIR,
        check=True,
    )
