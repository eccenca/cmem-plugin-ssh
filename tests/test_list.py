"""Tests for list plugin"""

import re

import pytest
from cmem_plugin_base.testing import TestExecutionContext, TestPluginContext
from paramiko import AuthenticationException

from cmem_plugin_ssh.autocompletion import DirectoryParameterType
from cmem_plugin_ssh.list import ListFiles
from tests.conftest import TestingEnvironment


def test_private_key_with_wrong_password(testing_environment: TestingEnvironment) -> None:
    """Test encrypted private key with wrong password failure"""
    with pytest.raises(AuthenticationException, match="Authentication failed."):
        ListFiles(
            hostname=testing_environment.hostname,
            port=testing_environment.port,
            username=testing_environment.username,
            private_key=testing_environment.private_key_with_password,
            password="wrong_password",  # noqa: S106
            authentication_method=testing_environment.authentication_method,
            path=testing_environment.path,
            regex=testing_environment.regex,
            no_subfolder=testing_environment.no_subfolder,
            error_handling=testing_environment.error_handling,
        )


def test_private_key_with_password_execution(testing_environment: TestingEnvironment) -> None:
    """Test autocompletion and base execution with a password encrypted private key"""
    plugin = ListFiles(
        hostname=testing_environment.hostname,
        port=testing_environment.port,
        username=testing_environment.username,
        private_key=testing_environment.private_key_with_password,
        password=testing_environment.password,
        authentication_method=testing_environment.authentication_method,
        path=testing_environment.path,
        regex=testing_environment.regex,
        no_subfolder=testing_environment.no_subfolder,
        error_handling=testing_environment.error_handling,
    )
    autocompletion = DirectoryParameterType(url_expand="", display_name="")
    depends_on = [
        plugin.hostname,
        plugin.port,
        plugin.username,
        plugin.private_key,
        plugin.password,
        plugin.authentication_method,
        plugin.path,
    ]
    autocompletion_result = autocompletion.autocomplete(
        query_terms=["volume"],
        depend_on_parameter_values=depends_on,
        context=TestPluginContext(),
    )
    assert len(autocompletion_result) > 0

    execution_result = plugin.execute(context=TestExecutionContext(), inputs=[])
    assert len(list(execution_result.entities)) == testing_environment.no_of_files


def test_plugin_wrong_hostname(testing_environment: TestingEnvironment) -> None:
    """Test plugin execution with an incorrect port"""
    with pytest.raises(TimeoutError, match="timed out"):
        ListFiles(
            hostname="123.45.6.78",
            port=testing_environment.port,
            username=testing_environment.username,
            private_key=testing_environment.private_key,
            password=testing_environment.password,
            authentication_method=testing_environment.authentication_method,
            path=testing_environment.path,
            regex=testing_environment.regex,
            no_subfolder=testing_environment.no_subfolder,
            error_handling=testing_environment.error_handling,
        )


def test_plugin_wrong_username(testing_environment: TestingEnvironment) -> None:
    """Test plugin execution with an incorrect port"""
    with pytest.raises(AuthenticationException, match="Authentication failed."):
        ListFiles(
            hostname=testing_environment.hostname,
            port=testing_environment.port,
            username="wrong_username",
            private_key=testing_environment.private_key,
            password=testing_environment.password,
            authentication_method=testing_environment.authentication_method,
            path=testing_environment.path,
            regex=testing_environment.regex,
            no_subfolder=testing_environment.no_subfolder,
            error_handling=testing_environment.error_handling,
        )


def test_plugin_wrong_port(testing_environment: TestingEnvironment) -> None:
    """Test plugin execution with an incorrect port"""
    with pytest.raises(OSError, match=re.escape(r"[Errno")):
        ListFiles(
            hostname=testing_environment.hostname,
            port=1234,
            username=testing_environment.username,
            private_key=testing_environment.private_key,
            password=testing_environment.password,
            authentication_method=testing_environment.authentication_method,
            path=testing_environment.path,
            regex=testing_environment.regex,
            no_subfolder=testing_environment.no_subfolder,
            error_handling=testing_environment.error_handling,
        )


def test_plugin_wrong_private_key(testing_environment: TestingEnvironment) -> None:
    """Test plugin execution with an incorrect private key"""
    with pytest.raises(ValueError, match="Unsupported private key format"):
        ListFiles(
            hostname=testing_environment.hostname,
            port=testing_environment.port,
            username=testing_environment.username,
            private_key="invalidkeymaterial",
            password="",
            authentication_method="key",
            path=testing_environment.path,
            regex=testing_environment.regex,
            no_subfolder=testing_environment.no_subfolder,
            error_handling=testing_environment.error_handling,
        )


def test_plugin_wrong_password(testing_environment: TestingEnvironment) -> None:
    """Test plugin execution with an incorrect private key"""
    with pytest.raises(AuthenticationException, match="Authentication failed."):
        ListFiles(
            hostname=testing_environment.hostname,
            port=testing_environment.port,
            username=testing_environment.username,
            private_key=testing_environment.private_key,
            password="1234",  # noqa: S106
            authentication_method="password",
            path=testing_environment.path,
            regex=testing_environment.regex,
            no_subfolder=testing_environment.no_subfolder,
            error_handling=testing_environment.error_handling,
        )


def test_plugin_password_authentication_only(testing_environment: TestingEnvironment) -> None:
    """Test plugin execution using only password (no private key)"""
    plugin = ListFiles(
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
    result_execution = plugin.execute(inputs=[], context=TestExecutionContext())
    assert len(list(result_execution.entities)) == testing_environment.no_of_files


def test_plugin_private_key_base_execution(testing_environment: TestingEnvironment) -> None:
    """Test basic plugin execution"""
    plugin = testing_environment.list_plugin
    result_execution = plugin.execute(inputs=[], context=TestExecutionContext())
    assert len(list(result_execution.entities)) == testing_environment.no_of_files


def test_plugin_execution_no_subfolder(testing_environment: TestingEnvironment) -> None:
    """Test plugin execution with no subfolder flag set"""
    plugin = testing_environment.list_plugin
    plugin.no_subfolder = True
    result_execution = plugin.execute(inputs=[], context=TestExecutionContext())
    assert len(list(result_execution.entities)) == 1


def test_plugin_no_matching_files(testing_environment: TestingEnvironment) -> None:
    """Test plugin when regex matches no files"""
    plugin = testing_environment.list_plugin
    plugin.regex = "nonmatchingpattern.*"
    result_execution = plugin.execute(inputs=[], context=TestExecutionContext())
    assert len(list(result_execution.entities)) == 0


def test_plugin_nonexistent_directory(testing_environment: TestingEnvironment) -> None:
    """Test plugin with a non-existing remote path"""
    plugin = testing_environment.list_plugin
    plugin.path = "non/existent/path"
    with pytest.raises(ValueError, match=r"\[Errno 2\] No such file"):
        plugin.execute(inputs=[], context=TestExecutionContext())


def test_preview_action(testing_environment: TestingEnvironment) -> None:
    """Test preview action"""
    plugin = testing_environment.list_plugin
    preview = plugin.preview_results()
    assert "RootFile.txt" in preview


def test_execution_denied_permission(testing_environment: TestingEnvironment) -> None:
    """Test execution with a not permitted file"""
    plugin = testing_environment.list_plugin
    plugin.path = "/etc"
    plugin.no_subfolder = True
    with pytest.raises(PermissionError, match=r"No access to '"):
        plugin.execute(inputs=[], context=TestExecutionContext())
