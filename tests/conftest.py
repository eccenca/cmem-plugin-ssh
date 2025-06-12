"""Pytest configuration"""

import shutil
import subprocess
import time
from dataclasses import dataclass
from os import environ
from pathlib import Path

import pytest

from cmem_plugin_ssh.list import ListFiles


def get_env_or_skip(key: str, message: str | None = None) -> str:
    """Get environment variable or skip test."""
    value = environ.get(key, "")
    if message is None:
        message = f"Skipped because the needed environment variable '{key}' is not set."
    if value == "":
        pytest.skip(message)
    return value


@dataclass
class TestingEnvironment:
    """Testing Environment"""

    __test__ = False

    hostname: str
    port: int
    username: str
    authentication_method: str
    private_key: str
    password: str
    path: str
    no_subfolder: bool
    list_plugin: ListFiles
    no_of_files: int = 11


@pytest.fixture
def testing_environment() -> TestingEnvironment:
    """Provide testing environment"""
    hostname = get_env_or_skip("SSH_HOSTNAME")
    port = int(get_env_or_skip("SSH_PORT"))
    username = get_env_or_skip("SSH_USERNAME")
    authentication_method = "key"
    private_key = get_env_or_skip("SSH_PRIVATE_KEY")
    password = get_env_or_skip("SSH_PASSWORD")
    path = "volume"
    no_subfolder = False
    list_plugin = ListFiles(
        hostname=hostname,
        port=port,
        username=username,
        private_key=private_key,
        path=path,
        password=password,
        authentication_method=authentication_method,
        no_subfolder=no_subfolder,
    )
    return TestingEnvironment(
        hostname=hostname,
        port=port,
        username=username,
        authentication_method=authentication_method,
        private_key=private_key,
        password=password,
        path=path,
        no_subfolder=no_subfolder,
        list_plugin=list_plugin,
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

    time.sleep(5)

    yield
    subprocess.run(  # noqa: S603
        [*get_compose_cmd(), "-f", DOCKER_COMPOSE_FILE, "down", "--rmi", "all"],
        cwd=DOCKER_COMPOSE_DIR,
        check=True,
    )
