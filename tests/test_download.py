"""Download plugin test suite"""

import tempfile
from pathlib import Path

import pytest
from cmem_plugin_base.testing import TestExecutionContext

from cmem_plugin_ssh.retrieval import SSHRetrieval
from tests.conftest import TestingEnvironment


def test_base_execution(testing_environment: TestingEnvironment) -> None:
    """Test download with no inputs given"""
    plugin = testing_environment.download_plugin
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin.download_dir = Path(tmpdir)
        result = plugin.execute(inputs=[], context=TestExecutionContext())
        assert len(list(result.entities)) == testing_environment.no_of_files


def test_download_restricted_file_error(testing_environment: TestingEnvironment) -> None:
    """Test download with error as error_handling"""
    plugin = testing_environment.download_plugin
    plugin.error_handling = "error"
    plugin.path = "/etc"
    plugin.regex = testing_environment.restricted_file
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin.download_dir = Path(tmpdir)
        with pytest.raises(ValueError, match=r"Permission denied"):
            plugin.execute(inputs=[], context=TestExecutionContext())


def test_download_restricted_file_warning(testing_environment: TestingEnvironment) -> None:
    """Test no input download with warning as error_handling policy"""
    plugin = testing_environment.download_plugin
    plugin.error_handling = "warning"
    plugin.path = "/etc"
    plugin.regex = "^.*$"

    retrieval = SSHRetrieval(
        ssh_client=plugin.ssh_client,
        no_subfolder=plugin.no_subfolder,
        regex=plugin.regex,
    )
    files = retrieval.list_files_parallel(
        files=[],
        context=None,
        path=plugin.path,
        error_handling=plugin.error_handling,
        no_access_files=[],
    )
    faulty_filename = [file.filename for file in files[1]]
    assert testing_environment.restricted_file in faulty_filename

    with tempfile.TemporaryDirectory() as tmpdir:
        plugin.download_dir = Path(tmpdir)
        result = plugin.execute(inputs=[], context=TestExecutionContext())
        assert len(list(result.entities)) > 0


def test_download_restricted_file_ignore(testing_environment: TestingEnvironment) -> None:
    """Test download with ignore-policy although the file is not permitted"""
    plugin = testing_environment.download_plugin
    plugin.error_handling = "ignore"
    plugin.path = "/etc"
    plugin.regex = testing_environment.restricted_file
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin.download_dir = Path(tmpdir)
        result = plugin.execute(inputs=[], context=TestExecutionContext())
        assert len(list(result.entities)) == 0
