import wx
import sys
import subprocess
from pathlib import Path

PKG_BASE = Path(__file__).resolve().parent

def locateWhl():
    for x in PKG_BASE.glob("*.whl"):
        return x.resolve()

def extractPackageVersion(path):
    assert isinstance(path, Path)
    return path.name.split("-")[1]

def installBackend():
    dialog = None
    try:
        dialog = wx.ProgressDialog("Please wait", "Installing Prusaman backend")
        dialog.Show()
        dialog.Pulse()

        p = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", locateWhl()],
            stderr=subprocess.PIPE, stdout=subprocess.PIPE,
            universal_newlines=True)
        while True:
            try:
                dialog.Pulse()
                retcode = p.wait(0.05)
                break
            except subprocess.TimeoutExpired:
                continue
        out = p.stdout.read()
        err = p.stdout.read()
        if retcode != 0:
            raise RuntimeError(f"{out}\n{err}")
    except Exception as e:
        wx.MessageBox(
            "Prusaman backend installation failed:\n\n" + str(e),
            "Error Prusaman backend",
            style = wx.OK | wx.ICON_ERROR)
        return
    finally:
        if dialog is not None:
            dialog.Destroy()

    wx.MessageBox(
        "Installation successfull. Please restart Pcbnew.",
        "Success",
        style = wx.OK | wx.ICON_INFORMATION)

try:
    import prusaman

    installedVersion = prusaman.__version__
    availableVersion = extractPackageVersion(locateWhl())

    if installedVersion != availableVersion:
        result = wx.MessageBox(
            f"Prusaman package expects backend version {availableVersion}, however, "
            f"version {installedVersion} is installed.\n\n"
            f"Do you wish to install {availableVersion}?",
            "Prusaman backend version mismatch",
            style = wx.YES_NO | wx.ICON_QUESTION)
        if result == wx.YES:
            installBackend()

    import prusaman.gui
    prusaman.gui.registerPlugins()
except ImportError:
    result = wx.MessageBox(
        "Prusaman is installed via PCM, but it is missing backend.\n\n" +
        "Do you want to install it?",
        "Missing Prusaman backend",
        style = wx.YES_NO | wx.ICON_QUESTION)
    if result == wx.YES:
        installBackend()
except Exception as e:
    import traceback
    tb = traceback.format_exc()
    wx.MessageBox(
        "Prusaman detected unexpected error:\n\n" + str(tb),
        "Unexpected error",
        style = wx.OK | wx.ICON_ERROR)

