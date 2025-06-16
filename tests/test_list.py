"""Tests for list plugin"""

import pytest
from cmem_plugin_base.testing import TestExecutionContext, TestPluginContext
from paramiko import SSHException

from cmem_plugin_ssh.autocompletion import DirectoryParameterType
from cmem_plugin_ssh.list import ListFiles
from tests.conftest import TestingEnvironment


def test_plugin_wrong_private_key(testing_environment: TestingEnvironment) -> None:
    """Test plugin execution with an incorrect private key"""
    with pytest.raises(SSHException, match="not a valid RSA private key file"):
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
    )
    result_execution = plugin.execute(inputs=[], context=TestExecutionContext())
    assert len(list(result_execution.entities)) == testing_environment.no_of_files


def test_plugin_base_execution(testing_environment: TestingEnvironment) -> None:
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


def test_autocompletion(testing_environment: TestingEnvironment) -> None:
    """Test autocompletion for folders on ssh instance"""
    plugin = testing_environment.list_plugin
    depends_on = [
        plugin.hostname,
        plugin.port,
        plugin.username,
        plugin.private_key,
        plugin.password,
        plugin.authentication_method,
        plugin.path,
    ]
    autocompletion = DirectoryParameterType(url_expand="", display_name="")
    autocompletion_result = autocompletion.autocomplete(
        query_terms=["volume"],
        depend_on_parameter_values=depends_on,
        context=TestPluginContext(),
    )

    autocompletion_values = [a.value for a in autocompletion_result]
    assert "/home/testuser" in autocompletion_values
    assert "/home/testuser/volume" in autocompletion_values
    assert "/home/testuser/volume/TextFiles" in autocompletion_values
    assert "/home/testuser/volume/MoreTextFiles" in autocompletion_values

    autocompletion_result = autocompletion.autocomplete(
        query_terms=[""],
        depend_on_parameter_values=depends_on,
        context=TestPluginContext(),
    )
    autocompletion_values = [a.value for a in autocompletion_result]
    assert "/home/testuser" in autocompletion_values
    assert "/home/testuser/volume" in autocompletion_values
    assert "/home/testuser/volume/TextFiles" in autocompletion_values
    assert "/home/testuser/volume/MoreTextFiles" in autocompletion_values

    autocompletion_result = autocompletion.autocomplete(
        query_terms=["volume/MoreTextFiles"],
        depend_on_parameter_values=depends_on,
        context=TestPluginContext(),
    )

    autocompletion_values = [a.value for a in autocompletion_result]
    assert "/home/testuser/volume" in autocompletion_values
    assert "/home/testuser/volume/MoreTextFiles" in autocompletion_values
    assert "/home/testuser/volume/MoreTextFiles/EvenMoreFiles" in autocompletion_values
    assert "/home/testuser/volume/MoreTextFiles/EvenMoreFiles2" in autocompletion_values

    autocompletion_result = autocompletion.autocomplete(
        query_terms=[".."],
        depend_on_parameter_values=depends_on,
        context=TestPluginContext(),
    )

    autocompletion_values = [a.value for a in autocompletion_result]
    assert "/home/testuser" in autocompletion_values
    assert "/home" in autocompletion_values

    depends_on[6] = ""
    autocompletion_result = autocompletion.autocomplete(
        query_terms=[""],
        depend_on_parameter_values=depends_on,
        context=TestPluginContext(),
    )
    autocompletion_values = [a.value for a in autocompletion_result]
    assert "/home/testuser/volume" in autocompletion_values
    assert "/home/testuser/.ssh" in autocompletion_values
    assert "/home/testuser" in autocompletion_values


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
    with pytest.raises(FileNotFoundError):
        plugin.execute(inputs=[], context=TestExecutionContext())
