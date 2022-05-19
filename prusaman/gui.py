import shutil
import pcbnew
import wx
import textwrap
import prusaman
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import traceback
import sys
import subprocess

from .params import RESOURCES
from .dialogs.prusamanExport import PrusamanExportBase, ErrorDialogBase
from .project import PrusamanProject
from .manugenerator import Manugenerator, replaceDirectory
from .util import locatePythonInterpreter
from .wxAnyThread import anythread

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


class PrusamanExport(PrusamanExportBase):
    def __init__(self, projectPath, *args, **kwargs):
        super().__init__(parent=None, *args, **kwargs)

        self.SetIcon(wx.Icon(str(RESOURCES / "icons" / "exportIcon.png")))
        self.SetTitle(f"Prusaman Export  (version {prusaman.__version__})")
        self.versionLabel.SetLabel(f"Prusaman version ({prusaman.__version__})")

        self.projectPath = Path(projectPath)
        self.triggered = False
        self.oldLabel = ""

    def onExport(self, event):
        self.oldLabel = self.exportButton.GetLabelText()
        def abandon():
            self.exportButton.SetLabelText(self.oldLabel)
            self.exportButton.Enable()
        try:
            self.outputProgressbar.SetValue(0)
            self.outputText.SetValue("")
            self.exportButton.SetLabelText("Exporting...")
            self.exportButton.Disable()

            self.triggered = False

            if len(self.outDirSelector.GetPath()) == 0:
                raise RuntimeError("No output directory specified")
            outDir = Path(self.outDirSelector.GetPath()) / "Prusaman_Export"
            if outDir.exists():
                answer = wx.MessageBox(
                    f"The output directory {outDir} already exists. " + \
                    "Running export will remove all files in it. Continue?",
                    "Overwrite files in the output directory?",
                    wx.ICON_QUESTION | wx.YES_NO)
                if answer == wx.NO:
                    abandon()
                    return

            project = PrusamanProject(self.projectPath)
            t = Thread(target=self.doExportWork, daemon=True,
                       args=(outDir, project))
            t.start()
        except Exception as e:
            abandon()
            reportException(e, traceback.format_exc())

    def doExportWork(self, outDir, project):
        # We use temporary directory so we do not damage any existing files in
        # process. Once we are done, we atomically swap the directories
        tmpdir = Path(outDir).resolve()
        faileddir = tmpdir.parent / (tmpdir.name + "-failed")
        tmpdir = tmpdir.parent / (tmpdir.name + "-temp")

        shutil.rmtree(faileddir, ignore_errors=True)
        shutil.rmtree(tmpdir, ignore_errors=True)
        try:
            exception = None
            def work():
                nonlocal exception
                try:
                    generator = Manugenerator(project, tmpdir,
                                    reportInfo=self.onInfo,
                                    reportWarning=self.onWarning,
                                    askContinuation=self.onPrompt)
                    generator.make()
                except Exception as e:
                    exception = e
            self.onInfo("", "Starting export")
            t = Thread(target=work)
            t.start()
            while True:
                wx.CallAfter(lambda: self.outputProgressbar.Pulse())
                t.join(0.1)
                if not t.is_alive():
                    break
            if exception is not None:
                raise exception

            if self.werrorCheckbox.GetValue() and self.triggered:
                raise RuntimeError("Warnings were treated as errors.\nSee warnings in the output box.")

            Path(outDir).mkdir(parents=True, exist_ok=True)
            replaceDirectory(outDir, tmpdir)
            self.onInfo("", "Finished, all files were successfully generated.")

            wx.CallAfter(lambda: self.outputProgressbar.SetValue(self.outputProgressbar.GetRange()))
            wx.CallAfter(lambda: self.onFinish(outDir))
        except Exception as e:
            replaceDirectory(faileddir, tmpdir)
            self.onError("", f"Error occured: {e}\n\nBuild artifacts are stored in {faileddir}")
            reportException(e, traceback.format_exc())
            wx.CallAfter(lambda: self.outputProgressbar.SetValue(0))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
            wx.CallAfter(lambda: self.exportButton.SetLabelText(self.oldLabel))
            wx.CallAfter(lambda: self.exportButton.Enable())

    def onWarning(self, tag, message):
        self.triggered = True
        self.addMessage("Warning", tag, message)

    def onInfo(self, tag, message):
        self.addMessage("Info", tag, message)

    def onError(self, tag, message):
        self.addMessage("Error", tag, message)

    @anythread
    def onPrompt(self, tag, message):
        answer = wx.MessageBox(message, tag, wx.ICON_QUESTION | wx.YES_NO)
        return answer == wx.YES

    def addMessage(self, header, tag, message):
        if len(message) == 0:
            return
        BODY = 80
        wMessages = textwrap.wrap(message, BODY)
        head, *tail = wMessages
        wx.CallAfter(lambda:
            self.outputText.write(f"{header + ' ' + tag + ': ':>20}{head}\n"))
        if len(tail) > 0:
            wx.CallAfter(lambda:
                self.outputText.write(textwrap.indent("\n".join(tail), 20 * " ") + "\n"))

    def onFinish(self, outdir):
        answer = wx.MessageBox(
            f"Export finished successfully.\nDo you want to open the output directory {outdir}?",
            "Export finished",
            wx.ICON_QUESTION | wx.YES_NO)
        if answer == wx.NO:
            return
        wx.LaunchDefaultApplication(str(outdir))


class ExportPlugin(pcbnew.ActionPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exception = None
        self.traceback = None
        self.worker = None

    def defaults(self):
        self.name = "Prusaman: Export"
        self.category = "Prusaman"
        self.description = "Build manufacturing data"
        self.icon_file_name = str(RESOURCES / "icons" / "exportIcon.png")
        self.show_toolbar_button = True

    def Run(self):
        self.worker = Thread(target=self.backgroundRun, daemon=True)
        self.exception = None
        self.worker.start()
        self.watchWorker()

    def backgroundRun(self):
        try:
            if pcbnew.GetBoard().IsEmpty():
                raise RuntimeError("Cannot export when there is no board opened")
            boardPath = Path(pcbnew.GetBoard().GetFileName())
            projectPath = boardPath.resolve().parent

            # Due to problems in KiCAD leading to segfault, we have to run export in
            # a separate process.
            command = [locatePythonInterpreter(), "-c",
                f"from prusaman.gui import runExport; runExport('{projectPath.as_posix()}');"]
            p = subprocess.run(command, capture_output=True, encoding="utf-8")
            if p.returncode != 0:
                raise RuntimeError(f"Cannot run Prusaman dialog in a new process: {p.stdout}\n{p.stderr}")
        except Exception as e:
            self.exception = e
            self.traceback = traceback.format_exc()

    def watchWorker(self):
        if self.worker.is_alive():
            wx.CallLater(100, self.watchWorker)
        else:
            if self.exception:
                reportException(self.exception, self.traceback)


def registerPlugins():
    ExportPlugin().register()

def reportException(e, details):
    wx.CallAfter(lambda: ErrorDialog(e, details).ShowModal())

def runExport(path):
    app = wx.App()

    d = PrusamanExport(path)
    try:
        d.ShowModal()
    except Exception as e:
        reportException(e, traceback.format_exc())
    finally:
        d.Destroy()

if __name__ == "__main__":
    runExport(sys.argv[1])
