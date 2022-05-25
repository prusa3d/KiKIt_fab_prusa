import traceback
import pcbnew
import wx

from ..drc import DesignRules
from ..project import PrusamanProject
from ..params import RESOURCES
from .common import reportException

class SyncDesignRulesPlugin(pcbnew.ActionPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def defaults(self):
        self.name = "Prusaman: Sync Design Rules"
        self.category = "Prusaman"
        self.description = "Synchronize design rules"
        self.icon_file_name = str(RESOURCES / "icons" / "syncrules.png")
        self.show_toolbar_button = True

    def Run(self):
        try:
            board = pcbnew.GetBoard()
            project = PrusamanProject(board.GetFileName())
            if "TECHNOLOGY_PARAMS" not in project.textVars:
                raise RuntimeError("Cannot sync rules, the project misses TECHNOLOGY_PARAMS variable.")
            paramsName = project.textVars["TECHNOLOGY_PARAMS"]
            designRules = DesignRules.fromName(paramsName)

            result = wx.MessageBox(
                f"Do you want to change the board design rules to {paramsName}?",
                "Prusaman: Confirm design rules synchronization",
                style = wx.YES_NO | wx.ICON_QUESTION)
            if result == wx.NO:
                return
            d = board.GetDesignSettings()
            designRules.applyTo(d)
            board.GetDesignSettings().CloneFrom(d)
        except Exception as e:
            reportException(e, traceback.format_exc())
