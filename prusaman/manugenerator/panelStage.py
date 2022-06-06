import os
import subprocess
import pcbnew # type: ignore
import shutil
import glob
from pathlib import Path

from ..text import populateText
from ..params import RESOURCES
from ..export import makeGerbers
from ..util import locatePythonInterpreter, zipFiles
from .common import collectStandardLayers, BoardError


class PanelStageMixin:
    def _makePanelStage(self) -> None:
        panelName = self._fileName("PANEL")
        outdir = self._outputdir / panelName
        outdir.mkdir(parents=True)
        outfile = outdir / (panelName + ".kicad_pcb")
        gerberdir = outdir / (panelName + "-gerber")

        # Make the panel based on the configuration
        if self._project.has("kikit.json"):
            self._makeKikitPanel(outfile)
        elif self._project.has("panel.sh"):
            self._makeScriptPanel(outfile)
        elif self._project.has("panel/panel.kicad_pcb"):
            self._makeManualPanel(outfile)
        else:
            raise BoardError("No recipe to make panel. " + \
                "You miss one of kikit.json, panel.sh or panel/panel.kicad_pcb in the project.")

        panel = pcbnew.LoadBoard(str(outfile))
        self._ensurePassingDrc(panel, "generated panel")

        makeGerbers(source=panel, outdir=gerberdir, layers=collectStandardLayers)
        self._makeIbom(source=self._project.getBoard(), outdir=outdir)
        shutil.copyfile(RESOURCES / "datamatrix_znaceni_zbozi_v2.pdf",
                        outdir / "datamatrix_znaceni_zbozi_v2.pdf")
        self._makePanelReadme(outdir, boardPath=outfile)

        zipFiles(str(gerberdir) + ".zip", outdir, None,
            glob.glob(str(outdir / "*.pdf")) +
            glob.glob(str(outdir / "*.txt")) +
            glob.glob(str(outdir / "*.html")) +
            glob.glob(str(gerberdir / "*")))

    def _makePanelReadme(self, outdir: Path, boardPath: Path) -> None:
        try:
            with open(self._project.getPanelReadmeTemplate(), "r") as f:
                content = populateText(f.read(), pcbnew.LoadBoard(str(boardPath)), self._project.textVars["ID"])
        except FileNotFoundError as e:
            raise BoardError(f"Missing panel readme template. Please create the file {self._project.getPanelReadmeTemplate()}") from None
        with open(outdir / (self._fileName("PANEL") + "-README.txt"), "w") as f:
            f.write(content)

    def _makeManualPanel(self, output: Path) -> None:
        source = self._project.getDir() / "panel" / "panel.kicad_pcb"
        try:
            shutil.copyfile(source, output)
        except FileNotFoundError:
            raise BoardError(f"Cannot copy {source} into final destination")

    def _makeKikitPanel(self, output: Path) -> None:
        self._reportInfo("KIKIT", "Starting panel")

        cfgFile = self._project.getDir() / "kikit.json"
        env = os.environ
        env["PRUSAMAN_SOURCE_PROJECT"] = str(self._project.getDir())
        input = self._project.getBoard()

        command = [locatePythonInterpreter(), "-m", "kikit.ui", "panelize",
                        "-p", str(cfgFile),
                        str(input), str(output)]

        r = subprocess.run(command, encoding="utf-8",
            capture_output=True, cwd=self._project.getDir(), env=env)
        if len(r.stdout) != 0:
            self._reportInfo("KIKIT", r.stdout)
        if len(r.stderr) != 0:
            self._reportWarning("KIKIT", r.stderr)
        if r.returncode != 0:
            raise BoardError(f"Cannot make KiKit panel. Error code {r.returncode}.")
        self._reportInfo("KIKIT", "Panel finished")


    def _makeScriptPanel(self, output: Path) -> None:
        command = [str(self._project / "panel.sh"), str(self._project.getBoard()), str(output)]
        result = subprocess.run(command, capture_output=True)
        stdout = result.stdout.decode("utf-8")
        stderr = result.stderr.decode("utf-8")
        if result.returncode != 0:
            message = f"The script for building panel {command[0]} failed " + \
                      f"with code {result.returncode} and output:\n{stdout}\n{stderr}"
            raise BoardError(message)
        self._reportInfo("PANEL_SCRIPT", stdout)
        self._reportWarning("PANEL_SCRIPT", stderr)
