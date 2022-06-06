import glob
from pathlib import Path
from typing import Set

import pcbnew

from ..export import makeGerbers
from ..params import MILL_RELEVANT_FOOTPRINTS
from ..util import zipFiles
from ..text import populateText


def preserveOnlyOutline(board: pcbnew.BOARD, allowedFootprints: Set[str]) -> None:
    toDelete = []
    for x in board.GetFootprints():
        if x.GetFPID().GetUniStringLibId() not in allowedFootprints:
            toDelete.append(x)
    for x in board.GetDrawings():
        if x.GetLayer() != pcbnew.Edge_Cuts:
            toDelete.append(x)
    for x in board.GetTracks():
        toDelete.append(x)
    for x in board.Zones():
        toDelete.append(x)

    for x in toDelete:
        board.Remove(x)

    targetNetinfo = board.GetNetInfo()
    targetNetinfo.RemoveUnusedNets()

class MillStageMixin:
    def _makeMillStage(self) -> None:
        self._reportInfo("MILL", "Starting MILL stage")
        panelName = self._fileName("PANEL")
        panelPath = self._outputdir / panelName / (panelName + ".kicad_pcb")

        millName = self._fileName("FREZA")
        outdir = self._outputdir / millName
        outdir.mkdir(parents=True, exist_ok=True)
        outfile = outdir / (millName + ".kicad_pcb")
        gerberdir = outdir / (millName + "-gerber")

        # Make the gerbers for board that has no features other than cuts
        panel = pcbnew.LoadBoard(str(panelPath))
        preserveOnlyOutline(panel, set(MILL_RELEVANT_FOOTPRINTS))
        pcbnew.SaveBoard(str(outfile), panel)
        makeGerbers(panel, gerberdir, lambda _: set([pcbnew.Edge_Cuts]))
        self._makeMillReadme(outdir, panel)
        zipFiles(str(outdir / (millName + ".zip")), outdir, None,
            glob.glob(str(outdir / "*.txt")) +
            glob.glob(str(outdir / "*.html")) +
            glob.glob(str(gerberdir / "*")))
        self._reportInfo("MILL", "Mill stage finished")

    def _makeMillReadme(self, outdir: Path, panel: pcbnew.BOARD) -> None:
        try:
            with open(self._project.getMillReadmeTemplate(), "r") as f:
                content = populateText(f.read(), panel, self._project.textVars["ID"])
        except FileNotFoundError as e:
            raise BoardError(f"Missing mill readme template. Please create the file {self._project.getMillReadmeTemplate()}") from None
        with open(outdir / (self._fileName("FREZA") + "-README.txt"), "w") as f:
            f.write(content)
