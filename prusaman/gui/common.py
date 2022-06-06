import wx
from ..dialogs.prusamanExport import ErrorDialogBase
from ..manugenerator import BoardError

class ErrorDialog(ErrorDialogBase):
    def __init__(self, error, details, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.errorMessage.SetLabelText(f"Unexpected error: {error}\nThis is a probably bug, please report and attach stacktrace below.")
        self.errorDetails.SetValue(details)
        self.SetMinSize(wx.Size(450, -1))
        self.Fit()

    def handleOk(self, event):
        super().handleOk(event)
        self.Close()

    def handleExpansion(self, event):
        super().handleExpansion(event)
        self.SetMinSize(wx.Size(450, -1))

def userInputMessageBox(message):
    wx.MessageBox(
        f"{message}\n\nPlease check log for further detail and correct the input project.",
        "Prusaman: Source data error",
        style = wx.OK | wx.ICON_ERROR | wx.STAY_ON_TOP)

def reportException(e, details):
    if isinstance(e, BoardError):
        wx.CallAfter(lambda: userInputMessageBox(str(e)))
    else:
        wx.CallAfter(lambda: ErrorDialog(e, details).ShowModal())
