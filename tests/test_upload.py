"""Upload ssh files workflow task test suite"""

from cmem_plugin_base.dataintegration.entity import Entities
from cmem_plugin_base.dataintegration.typed_entities.file import FileEntitySchema, LocalFile
from cmem_plugin_base.testing import TestExecutionContext

from tests.conftest import TestingEnvironment


def test_upload(testing_environment: TestingEnvironment) -> None:
    schema = FileEntitySchema()
    files = [LocalFile(path="../docker/volume/RootFile.txt", mime="")]
    entities = [schema.to_entity(file) for file in files]
    input_entities = Entities(entities=iter(entities), schema=schema)

    upload_plugin = testing_environment.upload_plugin
    upload_plugin.path = "/tmp"
    result = upload_plugin.execute(inputs=[input_entities], context=TestExecutionContext())
    assert len(list(result.entities)) == 1
