"""Tests for list plugin"""

from cmem_plugin_base.testing import TestExecutionContext, TestPluginContext

from cmem_plugin_ssh.autocompletion import DirectoryParameterType
from tests.conftest import TestingEnvironment


def test_ssh(testing_environment: TestingEnvironment) -> None:
    """Test ssh basic configuration"""
    plugin = testing_environment.list_plugin
    autocompletion = DirectoryParameterType("", "")
    result = autocompletion.autocomplete(
        context=TestPluginContext(),
        query_terms=[""],
        depend_on_parameter_values=[
            plugin.hostname,
            plugin.port,
            plugin.username,
            plugin.private_key,
            plugin.password,
            plugin.authentication_method,
            plugin.path,
        ],
    )
    assert len(result) > 0

    plugin.path = "test_2"
    result_execution = plugin.execute(inputs=[], context=TestExecutionContext())

    assert len(list(result_execution.entities)) > 0
