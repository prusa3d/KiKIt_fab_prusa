from .make import ExportPlugin
from .sync3d import Sync3DPlugin


def registerPlugins():
    ExportPlugin().register()
    Sync3DPlugin().register()

