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
    ]
    autocompletion = DirectoryParameterType(url_expand="", display_name="")
    autocompletion_result = autocompletion.autocomplete(
        query_terms=["volume"],
        depend_on_parameter_values=depends_on,
        context=TestPluginContext(),
    )

    autocompletion_values = [a.value for a in autocompletion_result]
    assert "/" in autocompletion_values

    autocompletion_result = autocompletion.autocomplete(
        query_terms=[""],
        depend_on_parameter_values=depends_on,
        context=TestPluginContext(),
    )
    autocompletion_values = [a.value for a in autocompletion_result]
    for f in [
        "/bin",
        "/boot",
        "/dev",
        "/etc",
        "/home",
        "/lib",
        "/lib64",
        "/media",
        "/mnt",
        "/opt",
        "/proc",
        "/restricted",
        "/root",
        "/run",
        "/sbin",
        "/srv",
        "/sys",
        "/tmp",  # noqa : S108
        "/usr",
        "/var",
        "/",
    ]:
        assert f in autocompletion_values

    autocompletion_result = autocompletion.autocomplete(
        query_terms=["/home/testuser/volume/MoreTextFiles/"],
        depend_on_parameter_values=depends_on,
        context=TestPluginContext(),
    )

    autocompletion_values = [a.value for a in autocompletion_result]
    for f in [
        "/home/testuser/volume/MoreTextFiles/EvenMoreFiles",
        "/home/testuser/volume/MoreTextFiles/EvenMoreFiles2",
        "/home/testuser/volume/MoreTextFiles",
    ]:
        assert f in autocompletion_values

    autocompletion_result = autocompletion.autocomplete(
        query_terms=["/bin"],
        depend_on_parameter_values=depends_on,
        context=TestPluginContext(),
    )

    autocompletion_values = [a.value for a in autocompletion_result]
    for f in ["/bin", "/sbin", "/"]:
        assert f in autocompletion_values

    autocompletion_result = autocompletion.autocomplete(
        query_terms=["/home/testuser/vol"],
        depend_on_parameter_values=depends_on,
        context=TestPluginContext(),
    )

    autocompletion_values = [a.value for a in autocompletion_result]
    for f in ["/home/testuser/volume", "/home/testuser"]:
        assert f in autocompletion_values

    with pytest.raises(ValueError, match=r"Permission denied"):
        autocompletion.autocomplete(
            query_terms=["/restricted/"],
            depend_on_parameter_values=depends_on,
            context=TestPluginContext(),
        )


def test_path_autocompletion_order(testing_environment: TestingEnvironment) -> None:
    """Test correct order for autocompleted path suggestions"""
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
        query_terms=["/home/testuser/volume/"],
        depend_on_parameter_values=depends_on,
        context=TestPluginContext(),
    )
    assert "/home/testuser/volume/MoreTextFiles" in autocompletion_result[0].label
    assert "/home/testuser/volume/TextFiles" in autocompletion_result[1].label
    assert "home/testuser/volume" in autocompletion_result[2].label
