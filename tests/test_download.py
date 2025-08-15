"""Download plugin test suite"""

import pytest
from cmem_plugin_base.testing import TestExecutionContext

from cmem_plugin_ssh.download import DownloadFiles
from cmem_plugin_ssh.retrieval import SSHRetrieval
from tests.conftest import TestingEnvironment


def test_base_execution(testing_environment: TestingEnvironment) -> None:
    """Test download with no inputs given"""
    plugin = testing_environment.download_plugin
    result = plugin.execute(inputs=[], context=TestExecutionContext())
    assert len(list(result.entities)) == testing_environment.no_of_files


def test_download_restricted_file_error(testing_environment: TestingEnvironment) -> None:
    """Test download with error as error_handling"""
    plugin = testing_environment.download_plugin
    plugin.error_handling = "error"
    plugin.path = "/etc"
    plugin.regex = testing_environment.restricted_file
    with pytest.raises(ValueError, match=r"Permission denied"):
        plugin.execute(inputs=[], context=TestExecutionContext())


def test_download_restricted_file_warning(testing_environment: TestingEnvironment) -> None:
    """Test no input download with warning as error_handling policy"""
    plugin = testing_environment.download_plugin
    plugin.error_handling = "warning"
    plugin.path = "/etc"
    plugin.regex = "^.*$"
    plugin._initialize_ssh_and_sftp_connections()  # noqa: SLF001

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

    result = plugin.execute(inputs=[], context=TestExecutionContext())
    assert len(list(result.entities)) > 0


def test_download_restricted_file_ignore(testing_environment: TestingEnvironment) -> None:
    """Test download with ignore-policy although the file is not permitted"""
    plugin = testing_environment.download_plugin
    plugin.error_handling = "ignore"
    plugin.path = "/etc"
    plugin.regex = testing_environment.restricted_file
    result = plugin.execute(inputs=[], context=TestExecutionContext())
    assert len(list(result.entities)) == 0


def test_download_with_input(testing_environment: TestingEnvironment) -> None:
    """Test basic execution of download with given input from list plugin"""
    list_plugin = testing_environment.list_plugin
    download_plugin = testing_environment.download_plugin
    list_result = [list_plugin.execute(inputs=[], context=TestExecutionContext())]
    download_result = download_plugin.execute(inputs=list_result, context=TestExecutionContext())
    assert len(list(download_result.entities)) == testing_environment.no_of_files


def test_download_with_input_error(testing_environment: TestingEnvironment) -> None:
    """Test input download error when a file is not permitted for download"""
    list_plugin = testing_environment.list_plugin
    list_plugin.path = "/etc"
    list_plugin.regex = "restricted.txt"
    list_plugin.error_handling = "ignore"
    download_plugin = testing_environment.download_plugin
    download_plugin.error_handling = "error"
    list_result = [list_plugin.execute(inputs=[], context=TestExecutionContext())]
    with pytest.raises(ValueError, match=r"Permission denied"):
        download_plugin.execute(inputs=list_result, context=TestExecutionContext())


def test_download_with_input_ignore(testing_environment: TestingEnvironment) -> None:
    """Test ignore option with one file as input that user has no permission, the result is empty"""
    list_plugin = testing_environment.list_plugin
    list_plugin.path = "/etc"
    list_plugin.regex = "^.*(txt)$"
    list_plugin.error_handling = "ignore"
    list_result = [list_plugin.execute(inputs=[], context=TestExecutionContext())]

    download_plugin = testing_environment.download_plugin
    download_plugin.error_handling = "ignore"
    download_results = download_plugin.execute(inputs=list_result, context=TestExecutionContext())
    assert len(list(download_results.entities)) == 0


def test_download_with_input_warning(testing_environment: TestingEnvironment) -> None:
    """Test warning option with one restricted file that gets shown in faulty entities"""
    list_plugin = testing_environment.list_plugin
    list_plugin.path = "/etc"
    list_plugin.regex = "^.*(txt)$"
    list_plugin.error_handling = "ignore"
    list_result = [list_plugin.execute(inputs=[], context=TestExecutionContext())]

    download_plugin = testing_environment.download_plugin
    download_plugin.error_handling = "warning"
    download_plugin._initialize_ssh_and_sftp_connections()  # noqa: SLF001
    downloaded_entities, faulty_entities = download_plugin.download_with_input(
        inputs=list_result, context=TestExecutionContext()
    )
    assert len(list(downloaded_entities)) == 0
    assert len(list(faulty_entities)) == 1

    download_results = download_plugin.execute(inputs=list_result, context=TestExecutionContext())
    assert len(list(download_results.entities)) == 0


def test_plugin_password_authentication_only(testing_environment: TestingEnvironment) -> None:
    """Test plugin execution using only password (no private key)"""
    plugin = DownloadFiles(
        hostname=testing_environment.hostname,
        port=testing_environment.port,
        username=testing_environment.username,
        password=testing_environment.password,
        private_key="",
        authentication_method="password",
        path=testing_environment.path,
        regex=testing_environment.regex,
        no_subfolder=testing_environment.no_subfolder,
        error_handling=testing_environment.error_handling,
    )
    assert plugin is not None
