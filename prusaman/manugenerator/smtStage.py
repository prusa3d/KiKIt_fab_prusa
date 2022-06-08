import csv
import glob
import os
from itertools import chain
from pathlib import Path
from typing import List, TextIO, Tuple
from kikit.eeschema_v6 import (Symbol, extractComponents,  # type: ignore
                               getField, getReference)

import pcbnew # type: ignore


from .common import naturalComponetKey, layerToSide, BoardError
from ..util import zipFiles, defaultTo
from ..export import makeDxf
from ..params import GLUE_STAMPS

def renderHolesToEdges(board: pcbnew.BOARD) -> None:
    """
    Removes all drill holes from the board and replaces them with graphical
    items
    """
    toDelete = []
    for f in board.GetFootprints():
        delete = False
        for p in f.Pads():
            if p.GetAttribute() not in [pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH]:
                continue
            if p.GetDrillShape() != pcbnew.PAD_DRILL_SHAPE_CIRCLE:
                raise NotImplementedError("Non-circular holes are not supported")
            dia = p.GetDrillSizeX()
            pos = p.GetPosition()

            circle = pcbnew.PCB_SHAPE()
            circle.SetWidth(pcbnew.FromMM(0.1))
            circle.SetShape(pcbnew.SHAPE_T_CIRCLE)
            circle.SetLayer(pcbnew.Edge_Cuts)
            circle.SetCenter(pos)
            circle.SetEnd(pcbnew.wxPoint(pos[0] + dia // 2, pos[1]))
            board.Add(circle)
            delete = True
        if delete:
            toDelete.append(f)

    for x in toDelete:
        board.Remove(x)

def sortGlueStamps(stamps: List[Tuple[pcbnew.wxPoint, int]]) -> List[Tuple[pcbnew.wxPoint, int]]:
    """
    Given a list of stamp positions and sizes return a new list that sorts them
    in order to minimize travel distance
    """
    from python_tsp.distances import euclidean_distance_matrix  # type: ignore
    from python_tsp.heuristics import solve_tsp_local_search  # type: ignore

    distMatrix = euclidean_distance_matrix([x[0] for x in stamps])
    perm, _ = solve_tsp_local_search(distMatrix, list(range(len(stamps))))
    return [stamps[i] for i in perm]


class SmtStageMixin:
    def _makeSmtStage(self) -> None:
        self._reportInfo("SMT", "Starting SMT stage")
        smtName = self._fileName("SMT")
        outdir = self._outputdir / smtName
        outdir.mkdir(parents=True, exist_ok=True)

        posName = outdir / (self._project.getName() + "-all-pos.csv")
        zipName = outdir / (self._project.getName() + "-BOM-SMT.zip")

        self._makesmtStageDxf(outdir)
        self._makeIbom(self._project.getBoard(), outdir)

        bomFilter = self._bomFilter

        bom = extractComponents(str(self._project.getSchema()))
        bom = [x for x in bom if bomFilter.assemblyFilter(x)]
        self._checkAnnotation(bom)
        bom.sort(key=naturalComponetKey)

        with open(posName, "w", newline="") as posFile:
            self._makeSmtPosFile(posFile, bom, self._project.getBoard())

        zipFiles(zipName, outdir, None,
            glob.glob(str(outdir / "*.txt")) +
            glob.glob(str(outdir / "*.html")) +
            glob.glob(str(outdir / "*.csv")) +
            glob.glob(str(outdir / "*.dxf")))

        panelName = self._fileName("PANEL")
        panelPath = self._outputdir / panelName / (panelName + ".kicad_pcb")

        self._makeGlueStamps(outdir, panelPath)
        self._reportInfo("SMT", "SMT stage finished")

    def _makesmtStageDxf(self, outdir: Path) -> None:
        millName = self._fileName("FREZA")
        strippedPanelName = self._outputdir / millName / (millName + ".kicad_pcb")
        strippedPanel = pcbnew.LoadBoard(str(strippedPanelName))
        renderHolesToEdges(strippedPanel)
        makeDxf(strippedPanel, outdir, lambda _: set([pcbnew.Edge_Cuts]))
        # Hacky way to replace a layer. However, for KiCAD boards with only
        # outlines it seems safe, and also, saves and external dependency in the
        # form of a DXF parsing library
        for f in os.listdir(outdir):
            if not f.endswith(".dxf"):
                continue
            with open(outdir / f, "r") as dxfFile:
                content = dxfFile.read()
            content = content.replace("\nBLACK\n", "\n0\n")
            with open(outdir / f, "w") as dxfFile:
                dxfFile.write(content)

    def _makeSmtPosFile(self, posFile: TextIO, bom: List[Symbol],
                        boardPath: Path) -> None:
        sourceBoard = pcbnew.LoadBoard(str(boardPath))
        writer = csv.writer(posFile)
        writer.writerow(["Ref", "ID", "Val", "Package", "PosX", "PosY", "Rot", "Side"])
        for item in bom:
            ref = getReference(item)
            id = getField(item, "ID")
            if id is None:
                self._userFail(f"Component {ref} has no ID but should be populated")

            f = sourceBoard.FindFootprintByReference(getReference(item))
            if f is None:
                self._reportWarning("SMT POS", f"Reference {ref} is present in schematics, " + \
                                    "but not in board. Ignoring.")
            pos = f.GetPosition()
            fpid = f.GetFPID()
            writer.writerow([
                f.GetReference(),
                id,
                f.GetValue(),
                fpid.GetUniStringLibItemName(),
                pcbnew.ToMM(pos[0]),
                -pcbnew.ToMM(pos[1]),
                ((f.GetOrientation()) % 3600) / 10,
                layerToSide(f.GetLayer())
            ])

    def _makeSmtBomFile(self, bomFile: TextIO, bom: List[Symbol]) -> None:
        def required(symbol: Symbol, field: str) -> str:
            v = getField(symbol, field)
            if v is None:
                self._userFail(f"{getReference(symbol)} is missing required field {field}")
            assert isinstance(v, str)
            return v

        def recommended(symbol: Symbol, field: str) -> str:
            v = getField(symbol, field)
            if v is None:
                self._reportWarning("BOM", f"{getReference(symbol)} is missing recommended field {field}")
            return defaultTo(v, "")

        def optional(symbol: Symbol, field: str) -> str:
            return defaultTo(getField(symbol, field), "")

        writer = csv.writer(bomFile)
        writer.writerow(["Reference", "Value", "Footprint", "Datasheet", "ID", "part_value", "req", "alt"])
        for symbol in bom:
            writer.writerow([
                getReference(symbol),
                required(symbol, "Value"),
                required(symbol, "Footprint"),
                recommended(symbol, "Datasheet"),
                recommended(symbol, "ID"),
                recommended(symbol, "part_value"),
                recommended(symbol, "req"),
                optional(symbol, "alt")
            ])

    def _makeGlueStamps(self, outdir: Path, panelPath: Path) -> None:
        panel = pcbnew.LoadBoard(str(panelPath))
        glueStamps = self._collectGlueStamps(panel)
        if len(glueStamps) == 0:
            return
        glueStamps = sortGlueStamps(glueStamps)
        glueName = outdir / (self._project.getName() + "-PANEL-glue-pos.csv")
        with open(glueName, "w", newline="") as f:
            writer = csv.writer(f)
            for i, (pos, dia) in enumerate(glueStamps):
                stamp = GLUE_STAMPS[dia]
                writer.writerow([
                    f"site{i:3}",
                    pcbnew.ToMM(pos[0]),
                    pcbnew.ToMM(pos[1]),
                    stamp.stepsForward,
                    stamp.stepsBackwards,
                    stamp.type,
                    pcbnew.ToMM(stamp.spacing)])

    def _collectGlueStamps(self, board: pcbnew.BOARD) -> List[Tuple[pcbnew.wxPoint, int]]:
        """
        Collect glue stamps from the board. If there are unsupported stamp shapes
        or sizes, raise error. Return list of tuples(position, diameter).
        """
        from pcbnew import ToMM, wxPoint

        stamps: List[Tuple[wxPoint, int]] = []

        candidates = board.GetDrawings()
        for f in board.GetFootprints():
            candidates = chain(candidates, f.GraphicalItems())
            # TBA: At the moment, we ignore pads as there is no API. We could
            # read it from a file...
            # for p in f.Pads():
            #     print(type(p.GetPrimitives()))
            #     candidates = chain(candidates, list(p.GetPrimitives()))
        error = False
        for item in candidates:
            if not isinstance(item, pcbnew.PCB_SHAPE) or item.GetLayer() not in [pcbnew.F_Adhes, pcbnew.B_Adhes]:
                continue
            shape = item.GetShape()
            if shape != pcbnew.SHAPE_T_CIRCLE:
                pos = item.GetStart()
                self._reportError("GLUE", f"Unsupported adhesive shape ({item.ShowShape()}) at ({ToMM(pos[0]), ToMM(pos[1])})")
                error = True
                continue
            pos = item.GetCenter()
            diameter = 2 * item.GetRadius()
            if diameter not in GLUE_STAMPS.keys():
                self._reportError("GLUE", f"Unsupported glue stamp with diameter {ToMM(diameter)} mm at ({ToMM(pos[0]), ToMM(pos[1])})")
                error = True
            stamps.append((pos, diameter))
        if error:
            raise BoardError(f"There are unsupported glue shapes on PCB.")
        return stamps
