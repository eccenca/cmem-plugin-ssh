"""Command execution workflow test suite"""

from pathlib import Path

from cmem_plugin_base.dataintegration.entity import Entities
from cmem_plugin_base.dataintegration.typed_entities.file import FileEntitySchema, LocalFile
from cmem_plugin_base.testing import TestExecutionContext

from tests.conftest import TestingEnvironment


def test_basic_command_execution(testing_environment: TestingEnvironment) -> None:
    """Test most basic execution of 'ls -al' command with no input"""
    execute_plugin = testing_environment.execute_plugin
    results = execute_plugin.execute(inputs=[], context=TestExecutionContext())
    assert len(list(results.entities)) == 1


def test_basic_command_execution_file_output(testing_environment: TestingEnvironment) -> None:
    """Test most basic execution of 'ls -al' command with no input"""
    execute_plugin = testing_environment.execute_plugin
    execute_plugin.output_method = "file_output"
    results = execute_plugin.execute(inputs=[], context=TestExecutionContext())
    assert len(list(results.entities)) == 1
    # need to also test that schema is right here


def test_basic_command_execution_input_files(testing_environment: TestingEnvironment) -> None:
    """Test execution with input files"""
    execute_plugin = testing_environment.execute_plugin
    execute_plugin.input_method = "file_input"
    execute_plugin.command = "cat"

    schema = FileEntitySchema()
    test_file_path = Path(__file__).parent.parent / "docker" / "volume" / "RootFile.txt"
    files = [LocalFile(path=str(test_file_path.resolve()), mime="")]
    entities = [schema.to_entity(file) for file in files]
    input_entities = Entities(entities=iter(entities), schema=schema)

    execute_result = execute_plugin.execute(inputs=[input_entities], context=TestExecutionContext())
    execute_result_exit_code = [e.values[0][0] for e in execute_result.entities]
    assert "0" in execute_result_exit_code


def test_basic_command_execution_input_files_file_output(
    testing_environment: TestingEnvironment,
) -> None:
    """Test execution with input files"""
    execute_plugin = testing_environment.execute_plugin
    execute_plugin.input_method = "file_input"
    execute_plugin.command = "cat"
    execute_plugin.output_method = "file_output"

    schema = FileEntitySchema()
    test_file_path = Path(__file__).parent.parent / "docker" / "volume" / "RootFile.txt"
    files = [LocalFile(path=str(test_file_path.resolve()), mime="")]
    entities = [schema.to_entity(file) for file in files]
    input_entities = Entities(entities=iter(entities), schema=schema)

    execute_result = execute_plugin.execute(inputs=[input_entities], context=TestExecutionContext())
    execute_result_file_type = [e.values[1][0] for e in execute_result.entities]
    assert "Local" in execute_result_file_type
