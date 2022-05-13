import wx
import sys
import os
import subprocess
from pathlib import Path

PKG_BASE = Path(__file__).resolve().parent

def ensurePip():
    r = subprocess.run([sys.executable, "-m", "pip", "--help"], capture_output=True)
    if r.returncode == 0:
        return
    subprocess.run([sys.executable, "-m", "ensurepip"], capture_output=True)
    r = subprocess.run([sys.executable, "-m", "pip", "--help"], capture_output=True)
    if r.returncode == 0:
        return
    raise RuntimeError(f"Missing pip, cannot install backend: {r.stdout}\n{r.stderr}")

def locateWhl():
    return [x.resolve() for x in PKG_BASE.glob("*.whl")]

def extractPackageVersion(path):
    assert isinstance(path, Path)
    return path.name.split("-")[1]

def locatePythonWrapper():
    e = Path(sys.executable)
    return str(e.parent / "kicad-cmd.bat")

def winEsc(s):
    return str(s).replace(" ", "^ ")

def installBackend():
    dialog = None
    try:
        dialog = wx.ProgressDialog("Please wait", "Installing Prusaman backend")
        dialog.Show()
        dialog.Pulse()

        if os.name == "nt":
            packages = " ".join([winEsc(x) for x in locateWhl()])
            p = subprocess.Popen(
                ["start", "cmd.exe", "/k", f"{winEsc(locatePythonWrapper())} && python -m pip install {packages} && EXIT /B"],
                stderr=subprocess.PIPE, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
                universal_newlines=True,
                shell=True)
        else:
            ensurePip()
            p = subprocess.Popen(
                [sys.executable, "-m", "pip", "install"] + locateWhl(),
                stderr=subprocess.PIPE, stdout=subprocess.PIPE,
                universal_newlines=True)
        while True:
            try:
                dialog.Pulse()
                retcode = p.wait(0.05)
                break
            except subprocess.TimeoutExpired:
                continue
        dialog.Hide()
        dialog.Destroy()
        dialog = None

        out = p.stdout.read()
        err = p.stderr.read()
        if retcode != 0:
            raise RuntimeError(f"({retcode}) {out}\n{err}")
    except Exception as e:
        wx.MessageBox(
            "Prusaman backend installation failed:\n\n" + str(e),
            "Error Prusaman backend",
            style = wx.OK | wx.ICON_ERROR | wx.STAY_ON_TOP)
        return
    finally:
        if dialog is not None:
            dialog.Hide()
            dialog.Destroy()

    wx.MessageBox(
        "Installation successfull. Please restart KiCAD so the changes takes effect.",
        "Prusaman",
        style = wx.OK | wx.ICON_INFORMATION | wx.STAY_ON_TOP)

try:
    import prusaman

    installedVersion = prusaman.__version__
    availableVersion = None
    for x in locateWhl():
        if x.name.startswith("Prusaman"):
            availableVersion = extractPackageVersion(x)
    if availableVersion is None:
        raise RuntimeError("Missing backend installation package. Probably corrupted installation.")

    if installedVersion != availableVersion:
        result = wx.MessageBox(
            f"Prusaman package expects backend version {availableVersion}, however, " + \
            f"version {installedVersion} is installed.\n\n" + \
            f"Do you wish to install {availableVersion}?",
            "Prusaman backend version mismatch",
            style = wx.YES_NO | wx.ICON_QUESTION)
        if result == wx.YES:
            installBackend()
    import prusaman.gui
    prusaman.gui.registerPlugins()
except ImportError:
    message = "Prusaman is installed via PCM, but it is missing backend.\n\n"
    message += "Do you want to install it?"
    if os.name == "nt":
        message += "\n\nThere will be a popup window during the installation"
    result = wx.MessageBox(
        message,
        "Missing Prusaman backend",
        style = wx.YES_NO | wx.ICON_QUESTION)
    if result == wx.YES:
        installBackend()
    try:
        import prusaman.gui
        prusaman.gui.registerPlugins()
    except Exception:
        # Let's try importing
        pass

except Exception as e:
    import traceback
    tb = traceback.format_exc()
    wx.MessageBox(
        "Prusaman detected unexpected error:\n\n" + str(tb),
        "Unexpected error",
        style = wx.OK | wx.ICON_ERROR)

