"""Upload ssh files workflow task test suite"""

from pathlib import Path

import pytest
from cmem_plugin_base.dataintegration.entity import Entities
from cmem_plugin_base.dataintegration.typed_entities.file import (
    FileEntitySchema,
    LocalFile,
)
from cmem_plugin_base.testing import TestExecutionContext

from cmem_plugin_ssh.upload import UploadFiles
from tests.conftest import TestingEnvironment


def test_upload_local_file(testing_environment: TestingEnvironment) -> None:
    """Test upload with a given input file"""
    schema = FileEntitySchema()
    test_file_path = Path(__file__).parent.parent / "docker" / "volume" / "RootFile.txt"
    files = [LocalFile(path=str(test_file_path.resolve()), mime="")]
    entities = [schema.to_entity(file) for file in files]
    input_entities = Entities(entities=iter(entities), schema=schema)

    upload_plugin = testing_environment.upload_plugin
    upload_plugin.path = "/tmp"  # noqa: S108
    result = upload_plugin.execute(inputs=[input_entities], context=TestExecutionContext())
    assert len(list(result.entities)) == 1


def test_no_input(testing_environment: TestingEnvironment) -> None:
    """Test error when no input was given to the workflow task"""
    upload_plugin = testing_environment.upload_plugin
    with pytest.raises(ValueError, match="No input was given!"):
        upload_plugin.execute(inputs=[], context=TestExecutionContext())


def test_upload_fail_missing_permission(testing_environment: TestingEnvironment) -> None:
    """Test error throwing when trying to upload to folder with no permission"""
    schema = FileEntitySchema()
    test_file_path = Path(__file__).parent.parent / "docker" / "volume" / "RootFile.txt"
    files = [LocalFile(path=str(test_file_path.resolve()), mime="")]
    entities = [schema.to_entity(file) for file in files]
    input_entities = Entities(entities=iter(entities), schema=schema)

    upload_plugin = testing_environment.upload_plugin
    upload_plugin.path = "/etc"
    with pytest.raises(ValueError, match=r"An error occurred during upload: "):
        upload_plugin.execute(inputs=[input_entities], context=TestExecutionContext())


def test_plugin_password_authentication_only(testing_environment: TestingEnvironment) -> None:
    """Test plugin execution using only password (no private key)"""
    plugin = UploadFiles(
        hostname=testing_environment.hostname,
        port=testing_environment.port,
        username=testing_environment.username,
        password=testing_environment.password,
        private_key="",
        authentication_method="password",
        path=testing_environment.path,
    )
    assert plugin is not None
