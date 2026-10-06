"""ForgeAI optional capability plugins.

Specialized plugins are registered here incrementally. The core plugin system is
present even when no specialist plugin is installed.
"""

from forgeai.core.plugin_manager import PluginManager
from forgeai.plugins.python_plugin import register_python_plugin


def register_builtin_plugins(manager: PluginManager) -> None:
    """Register specialist plugins shipped with this Forge build."""

    register_python_plugin(manager)
