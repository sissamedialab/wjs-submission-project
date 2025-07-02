from pathlib import Path
from typing import Any

from utils import plugins
from utils.logger import get_logger

logger = get_logger(__name__)

PLUGIN_NAME = "WJS submission"
DISPLAY_NAME = "WJS submission"
DESCRIPTION = "A plugin to manage submissions for WJS"
AUTHOR = "Nephila"
VERSION = "0.1"
SHORT_NAME = str(Path(__file__).parent.name)
JANEWAY_VERSION = "1.7"
MANAGER_URL = f"{SHORT_NAME}_manager"

# TODO: are we a "worflow" plugin?
# see https://janeway.readthedocs.io/en/latest/dev/plugins.html


class WJSSubmission(plugins.Plugin):
    """Plugin setup."""

    short_name = SHORT_NAME
    plugin_name = PLUGIN_NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    author = AUTHOR
    version = VERSION
    janeway_version = JANEWAY_VERSION
    manager_url = MANAGER_URL
    enabled = True
    # TODO: add here workflow-related attributes if necessary


def install():
    """Register the plugin instance."""
    WJSSubmission.install()


def hook_registry() -> dict[str, Any]:
    """Register hooks for current plugin."""
    return {}
