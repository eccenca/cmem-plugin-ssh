"""Download plugin test suite"""

import tempfile
from pathlib import Path

from cmem_plugin_base.testing import TestExecutionContext

from cmem_plugin_ssh.download import DownloadFiles
from tests.conftest import TestingEnvironment


def test_base_execution(testing_environment: TestingEnvironment) -> None:
    """Test download with no inputs given"""
    plugin = DownloadFiles(
        hostname=testing_environment.hostname,
        port=testing_environment.port,
        username=testing_environment.username,
        private_key=testing_environment.private_key_with_password,
        password=testing_environment.password,
        authentication_method=testing_environment.authentication_method,
        path=testing_environment.path,
        regex=testing_environment.regex,
        no_subfolder=testing_environment.no_subfolder,
        error_handling=testing_environment.error_handling
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin.download_dir = Path(tmpdir)
        result = plugin.execute(inputs=[], context=TestExecutionContext())
        assert len(list(result.entities)) == testing_environment.no_of_files
