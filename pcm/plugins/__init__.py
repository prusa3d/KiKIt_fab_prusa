import wx
import sys
import os
import subprocess
from pathlib import Path

PKG_BASE = Path(__file__).resolve().parent

def registerPlugins():
    pass

def locateWhl():
    wx.MessageBox(str(PKG_BASE), "Info 2")
    for x in PKG_BASE.glob("*.whl"):
        return x.resolve()

def extractPackageSemver(input):
    assert isinstance(input, Path)
    version = str(input[-1]).split("-")[1]
    return readSemver(version)

def readSemver(input):
    parts = input.split("+")[0].split(".")
    assert len(parts) == 3
    return tuple([int(x) for x in parts])

def installBackend():
    dialog = None
    try:
        dialog = wx.ProgressDialog("Please wait", "Installing Prusaman backend")
        dialog.Show()
        dialog.Pulse()

        wx.MessageBox(f"{[sys.executable, '-m', 'pip', 'install', locateWhl()]}", "Info")

        p = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", locateWhl()],
            stderr=subprocess.PIPE, stdout=subprocess.PIPE,
            universal_newlines=True
        )
        while True:
            try:
                dialog.Pulse()
                retcode = p.wait(0.1)
                break
            except subprocess.TimeoutExpired:
                continue
        out = p.stdout.read()
        err = p.stdout.read()
        if retcode != 0:
            raise RuntimeError(f"{out}\n{err}")



    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        wx.MessageBox(
            "Prusaman backend installation failed:\n\n" + str(tb),
            "Error Prusaman backend",
            style = wx.OK | wx.ICON_ERROR
        )
        return
    finally:
        if dialog is not None:
            dialog.Destroy()

    wx.MessageBox(
        "Installation successfull. Please restart Pcbnew.",
        "Success",
        style = wx.OK | wx.ICON_INFORMATION
    )


try:
    wx.MessageBox(
        "Trying",
        "Success",
        style = wx.OK | wx.ICON_INFORMATION
    )

    import prusaman

    installedVersion = readSemver(prusaman.__version__)
    availableVersion = extractPackageSemver(locateWhl())

    if installedVersion < availableVersion:
        result = wx.MessageBox(
            "Prusaman backend is out of date, update it?"
            "Outdated Prusaman backend",
            style = wx.YES_NO | wx.ICON_QUESTION
        )
        if result == wx.YES:
            installBackend()

    wx.MessageBox(
        "Running!",
        "Success",
        style = wx.OK | wx.ICON_INFORMATION
    )

    prusaman.gui.registerPlugins()
except ImportError:
    result = wx.MessageBox(
        "Prusaman is installed via PCM, but it is missing backend.\n\n" +
        "Do you want to install it?",
        "Missing Prusaman backend",
        style = wx.YES_NO | wx.ICON_QUESTION
    )
    if result == wx.YES:
        installBackend()
except Exception as e:
    import traceback
    tb = traceback.format_exc()
    wx.MessageBox(
        "Prusaman backend installation failed:\n\n" + str(tb),
        "Error Prusaman backend",
        style = wx.OK | wx.ICON_ERROR
    )
