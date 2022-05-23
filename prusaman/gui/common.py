import wx
from ..dialogs.prusamanExport import ErrorDialogBase

class ErrorDialog(ErrorDialogBase):
    def __init__(self, error, details, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.errorMessage.SetLabelText(f"Error: {error}")
        self.errorDetails.SetValue(details)
        self.SetMinSize(wx.Size(450, -1))
        self.Fit()

    def handleOk(self, event):
        super().handleOk(event)
        self.Close()

    def handleExpansion(self, event):
        super().handleExpansion(event)
        self.SetMinSize(wx.Size(450, -1))


def reportException(e, details):
    wx.CallAfter(lambda: ErrorDialog(e, details).ShowModal())
