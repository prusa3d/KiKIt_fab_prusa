from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

# Bring the plugins to the top level package
from .kikitPlugins import Tooling, Framing
tooling = Tooling
framing = Framing
