from .make import ExportPlugin
from .sync3d import Sync3DPlugin
from .syncrules import SyncDesignRulesPlugin


def registerPlugins():
    ExportPlugin().register()
    Sync3DPlugin().register()
    SyncDesignRulesPlugin().register()

