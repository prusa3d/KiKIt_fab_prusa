import traceback
import pcbnew
import wx

from ..params import RESOURCES
from ..sync3d import synchronize3D
from .common import reportException

class Sync3DPlugin(pcbnew.ActionPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def defaults(self):
        self.name = "Prusaman: Sync 3D"
        self.category = "Prusaman"
        self.description = "Synchronize visibility of 3D models"
        self.icon_file_name = str(RESOURCES / "icons" / "3dsync.png")
        self.show_toolbar_button = True

    def Run(self):
        try:
            board = pcbnew.GetBoard()
            synchronize3D(board)
            wx.MessageBox(
                f"3D models synchronized",
                "Prusaman",
                wx.ICON_INFORMATION | wx.OK)
        except Exception as e:
            reportException(e, traceback.format_exc())
