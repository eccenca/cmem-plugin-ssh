"""Tests for list plugin"""

from cmem_plugin_base.testing import TestExecutionContext

from tests.conftest import TestingEnvironment


def test_ssh(testing_environment: TestingEnvironment) -> None:
    """Test ssh basic configuration"""
    plugin = testing_environment.list_plugin
    result_execution = plugin.execute(inputs=[], context=TestExecutionContext())
    assert len(list(result_execution.entities)) == testing_environment.no_of_files
