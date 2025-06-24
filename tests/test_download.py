"""Download plugin test suite"""

import tempfile
from pathlib import Path

import pytest
from cmem_plugin_base.testing import TestExecutionContext

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
