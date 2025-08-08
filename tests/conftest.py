"""Pytest configuration"""

import logging
import shutil
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.image import DockerImage

from cmem_plugin_ssh.download import DownloadFiles
from cmem_plugin_ssh.execute_commands import ExecuteCommands
from cmem_plugin_ssh.list import ListFiles
from cmem_plugin_ssh.upload import UploadFiles
from docker.errors import APIError
from tests.fixtures import (
    SSH_HOSTNAME,
    SSH_PASSWORD,
    SSH_PRIVATE_KEY,
    SSH_PRIVATE_KEY_WITH_PASSWORD,
    SSH_USERNAME,
)

logger = logging.getLogger(__name__)


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
    input_method: str
    output_method: str
    command: str
    timeout: float
    restricted_file: str
    list_plugin: ListFiles
    download_plugin: DownloadFiles
    upload_plugin: UploadFiles
    execute_plugin: ExecuteCommands
    no_of_files: int = 12


@pytest.fixture
def testing_environment(ssh_test_container: DockerContainer) -> TestingEnvironment:
    """Provide testing environment"""
    hostname = SSH_HOSTNAME
    port = ssh_test_container.get_exposed_port(22)
    username = SSH_USERNAME
    authentication_method = "key"
    private_key = SSH_PRIVATE_KEY
    private_key_with_password = SSH_PRIVATE_KEY_WITH_PASSWORD
    password = SSH_PASSWORD
    error_handling = "error"
    path = "volume"
    regex = "^.*$"
    input_method = "no_input"
    output_method = "structured_output"
    command = "ls -al"
    timeout = 0
    restricted_file = "/etc/restricted.txt"
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
    upload_plugin = UploadFiles(
        hostname=hostname,
        port=port,
        username=username,
        private_key=private_key,
        path=path,
        password=password,
        authentication_method=authentication_method,
    )
    execute_plugin = ExecuteCommands(
        hostname=hostname,
        port=port,
        username=username,
        private_key=private_key,
        path=path,
        password=password,
        authentication_method=authentication_method,
        input_method=input_method,
        output_method=output_method,
        timeout=timeout,
        command=command,
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
        input_method=input_method,
        output_method=output_method,
        timeout=timeout,
        command=command,
        error_handling=error_handling,
        restricted_file=restricted_file,
        list_plugin=list_plugin,
        download_plugin=download_plugin,
        upload_plugin=upload_plugin,
        execute_plugin=execute_plugin,
    )


def get_compose_cmd() -> list[str]:
    """Get the correct compose command for environment"""
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return ["docker", "compose"]


DOCKER_DIR = Path(__file__).parent.parent / "docker"


@pytest.fixture(scope="session")
def ssh_test_container() -> Generator[DockerContainer, None, None]:
    """Start the SSH test container before tests and stop it after."""
    try:
        with (
            DockerImage(path=DOCKER_DIR, tag="cmem-plugin-openssh:latest", clean_up=False) as image,
            DockerContainer(str(image))
            .with_exposed_ports(22)
            .with_volume_mapping(DOCKER_DIR / "volume", "/home/testuser/volume", "rw") as container,
        ):
            yield container
    except APIError:
        logger.exception("Failed to cleanup Docker container")
