import os
from pcbnew import wxPointMM, FootprintLoad, UTF8, ToMM
from typing import Any, Dict, Iterable, Tuple
from kikit.plugin import FramingPlugin, ToolingPlugin, TextVariablePlugin
from kikit.text import Formatter
from kikit.panelize import Panel
from kikit.units import mm, readLength
from kikit.substrate import Substrate
from prusaman.params import RESOURCES
from prusaman.project import PrusamanProject
from shapely.geometry import LineString, box


def addPrusaFp(panel, name, position):
    footprint = FootprintLoad(str(RESOURCES / "prusalib.pretty"), name)

    fid = footprint.GetFPID()
    fid.SetLibNickname(UTF8("prusa_other"))
    footprint.SetFPID(fid)

    footprint.SetPosition(position)
    panel.board.Add(footprint)

class Tooling(ToolingPlugin):
    def buildTooling(self, panel: Panel) -> None:
        topLeft, topRight, bottomLeft, bottomRight = panel.panelCorners()
        addPrusaFp(panel, "hole4cutter-2mm", topLeft + wxPointMM(2.5, 2.5))
        addPrusaFp(panel, "hole4cutter-2mm", bottomRight + wxPointMM(-10, -2.5))
        addPrusaFp(panel, "hole4cutter-1,5mm", topRight + wxPointMM(-2.5, 2.5))
        addPrusaFp(panel, "hole4cutter-1,5mm", bottomLeft + wxPointMM(2.5, -2.5))

class Framing(FramingPlugin):
    def _spacing(self) -> Tuple[int, int]:
        layout = self.preset["layout"]
        if layout["type"] != "grid":
            raise RuntimeError("Prusaman framing plugin supports only grid pattern.")
        return layout["vspace"], layout["hspace"]

    def buildFraming(self, panel: Panel) -> Iterable[LineString]:
        vSpace, hSpace = self._spacing()
        panel.makeTightFrame(5 * mm, 2 * mm, vSpace, hSpace)
        panel.boardSubstrate.removeIslands()

        height = readLength(self.userArg)
        minx, miny, maxx, maxy = panel.panelBBox()
        currentHeight = maxy - miny
        if currentHeight > height:
            raise RuntimeError(f"The requested height {height} is smaller than the minimal panel height {ToMM(currentHeight)} mm")
        heightDiff = height - currentHeight
        panel.appendSubstrate(box(minx, maxy, maxx, maxy + heightDiff / 2))
        panel.appendSubstrate(box(minx, miny - heightDiff / 2, maxx, miny))
        panel.addCornerChamfers(1.5 * mm)

        return []

    def buildDummyFramingSubstrates(self, substrates: Iterable[Substrate]) -> Iterable[Substrate]:
        # We follow exactly what KiKit does:
        vSpace, hSpace = self._spacing()
        dummy = []
        minx, miny, maxx, maxy = substrates[0].bounds()
        for s in substrates:
            minx2, miny2, maxx2, maxy2 = s.bounds()
            minx = min(minx, minx2)
            miny = min(miny, miny2)
            maxx = max(maxx, maxx2)
            maxy = max(maxy, maxy2)
        width = 5 * mm
        # Note that the constructed substrates has to have a non-zero width/height.
        # If the width is zero, we break the input condition of the neighbor finding
        # algorithm (as there is no distinguishion between left and right side)
        if vSpace is not None:
            top = box(minx, miny - 2 * vSpace - width, maxx, miny - 2 * vSpace)
            bottom = box(minx, maxy + 2 * vSpace, maxx, maxy + 2 * vSpace + width)
            dummy.append(self.polygonToSubstrate(top))
            dummy.append(self.polygonToSubstrate(bottom))
        if hSpace is not None:
            left = box(minx - 2 * hSpace - width, miny, minx - 2 * hSpace, maxy)
            right = box(maxx + 2 * hSpace, miny, maxx + 2 * hSpace + width, maxy)
            dummy.append(self.polygonToSubstrate(left))
            dummy.append(self.polygonToSubstrate(right))
        return dummy

    def polygonToSubstrate(self, polygon):
        s = Substrate([])
        s.union(polygon)
        return s

class Text(TextVariablePlugin):
    def variables(self) -> Dict[str, Any]:
        try:
            project = PrusamanProject(os.environ["PRUSAMAN_SOURCE_PROJECT"])
        except KeyError:
            raise RuntimeError("Env variable PRUSAMAN_SOURCE_PROJECT not set") from None
        return {
            "boardId": project.textVars["ID"],
            "boardRevision": Formatter(lambda: project.board.GetTitleBlock().GetRevision())
        }
