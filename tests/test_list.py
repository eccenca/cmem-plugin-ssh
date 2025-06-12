"""Tests for list plugin"""

from cmem_plugin_base.testing import TestExecutionContext, TestPluginContext

from cmem_plugin_ssh.autocompletion import DirectoryParameterType
from tests.conftest import TestingEnvironment


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
    assert "/home/testuser/volume/.." in autocompletion_values
    assert "/home/testuser/volume/TextFiles" in autocompletion_values
    assert "/home/testuser/volume/MoreTextFiles" in autocompletion_values

    autocompletion_result = autocompletion.autocomplete(
        query_terms=[""],
        depend_on_parameter_values=depends_on,
        context=TestPluginContext(),
    )
    autocompletion_values = [a.value for a in autocompletion_result]
    assert "/home/testuser/volume/.." in autocompletion_values
    assert "/home/testuser/volume/TextFiles" in autocompletion_values
    assert "/home/testuser/volume/MoreTextFiles" in autocompletion_values

    autocompletion_result = autocompletion.autocomplete(
        query_terms=["volume/MoreTextFiles"],
        depend_on_parameter_values=depends_on,
        context=TestPluginContext(),
    )

    autocompletion_values = [a.value for a in autocompletion_result]
    assert "/home/testuser/volume/MoreTextFiles/.." in autocompletion_values
    assert "/home/testuser/volume/MoreTextFiles/EvenMoreFiles" in autocompletion_values
    assert "/home/testuser/volume/MoreTextFiles/EvenMoreFiles2" in autocompletion_values

    autocompletion_result = autocompletion.autocomplete(
        query_terms=[".."],
        depend_on_parameter_values=depends_on,
        context=TestPluginContext(),
    )

    autocompletion_values = [a.value for a in autocompletion_result]
    assert "/home/testuser" in autocompletion_values
    assert "/home/.." in autocompletion_values

    depends_on[6] = ""
    autocompletion_result = autocompletion.autocomplete(
        query_terms=[""],
        depend_on_parameter_values=depends_on,
        context=TestPluginContext(),
    )
    autocompletion_values = [a.value for a in autocompletion_result]
    assert "/home/testuser/volume" in autocompletion_values
    assert "/home/testuser/.ssh" in autocompletion_values
    assert "/home/testuser/.." in autocompletion_values
