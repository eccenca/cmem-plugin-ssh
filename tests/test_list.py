import os

from cmem_plugin_base.testing import TestPluginContext

from cmem_plugin_ssh.autocompletion import DirectoryParameterType
from cmem_plugin_ssh.list import ListFiles


def test_ssh() -> None:
    """Test ssh basic cfiguration"""
    plugin = ListFiles(
        hostname="85.215.151.19",
        port=22,
        username="lw",
        private_key=os.getenv("PRIVATE_KEY"),
        path="",
        password="",
        authentication_method="key"
    )
    print(plugin.authentication_method)
    autocompletion = DirectoryParameterType("", "")
    result = autocompletion.autocomplete(
        context=TestPluginContext(),
        query_terms=[""],
        depend_on_parameter_values=[plugin.hostname, 22, "lw", os.getenv("PRIVATE_KEY")],
    )
    for r in result:
        print(r)
