"""Autocompletion test suite"""
import pytest
from cmem_plugin_base.testing import TestPluginContext

from cmem_plugin_ssh.autocompletion import DirectoryParameterType
from tests.conftest import TestingEnvironment


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

    depends_on[6] = "/restricted"
    with pytest.raises(ValueError, match=r"Permission denied"):
        autocompletion.autocomplete(
            query_terms=["/restricted"],
            depend_on_parameter_values=depends_on,
            context=TestPluginContext(),
        )
