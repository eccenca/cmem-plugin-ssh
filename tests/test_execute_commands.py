"""Command execution workflow test suite"""

from cmem_plugin_base.testing import TestExecutionContext

from tests.conftest import TestingEnvironment


def test_ls_command(testing_environment: TestingEnvironment) -> None:
    """Test most basic execution of 'ls -al' command with no input"""
    execute_plugin = testing_environment.execute_plugin
    results = execute_plugin.execute(inputs=[], context=TestExecutionContext())
    assert len(list(results.entities)) == 1


def test_ls_command_file_output(testing_environment: TestingEnvironment) -> None:
    """Test most basic execution of 'ls -al' command with no input"""
    execute_plugin = testing_environment.execute_plugin
    execute_plugin.output_method = "file_output"
    results = execute_plugin.execute(inputs=[], context=TestExecutionContext())
    assert len(list(results.entities)) == 1
    # need to also test that schema is right here
