from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from itertools import chain
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union, TextIO

import pcbnew # type: ignore

from prusaman.bom import BomFilter, LegacyFilter, PnBFilter
from prusaman.netlist import exportIBomNetlist

from .configuration import PrusamanConfiguration
from .export import makeDxf, makeGerbers
from .params import GLUE_STAMPS, MILL_RELEVANT_FOOTPRINTS, RESOURCES
from .project import PrusamanProject
from .text import populateText
from .util import defaultTo, groupBy, splitOn, zipFiles, locatePythonInterpreter

T = TypeVar("T")
OutputReporter = Callable[[str, str], None]  # Takes TAG and message

def stderrReporter(tag: str, message: str) -> None:
    sys.stderr.write(f"{tag}: {message}\n")

def replaceDirectory(target: Union[Path, str], source: Union[Path, str]) -> None:
    shutil.rmtree(target)
    shutil.move(source, target)

from kikit.eeschema_v6 import Symbol, extractComponents, getField, getReference # type: ignore

def checkAnnotation(bom: List[Symbol]) -> None:
    unann = []
    wrongAnn = []
    for s in bom:
        ref = getReference(s)
        if "?" in ref:
            unann.append(ref)
            continue
        text, num = splitOn(ref, lambda x: not x.isdigit())
        if not num.isdigit():
            wrongAnn.append(ref)
    message = ""
    if len(unann) > 0:
        message += f"There are {len(unann)} components unannotated in the schematic\n"
    if len(wrongAnn) > 0:
        message += "The following components have invalid annotation: " + ", ".join(wrongAnn)
    if len(message) > 0:
        raise RuntimeError(message)

def naturalComponetKey(component: Symbol) -> Tuple[str, int]:
    text, num = splitOn(getReference(component), lambda x: not x.isdigit())
    return str(text), int(num)

def layerToSide(layer: int) -> str:
    if layer == pcbnew.F_Cu:
        return "top"
    if layer == pcbnew.B_Cu:
        return "bottom"
    raise RuntimeError(f"Got component with invalid layer {layer}")

def collectStandardLayers(board: pcbnew.BOARD) -> set[int]:
    layers = set([
        pcbnew.F_Mask,
        pcbnew.B_Mask,
        pcbnew.F_SilkS,
        pcbnew.B_SilkS,
        pcbnew.F_Paste,
        pcbnew.B_Paste,
        pcbnew.Edge_Cuts
    ])
    for layer in pcbnew.LSET_AllCuMask(board.GetCopperLayerCount()).CuStack():
        layers.add(layer)
    return layers

def preserveOnlyOutline(board: pcbnew.BOARD, allowedFootprints: set[str]) -> None:
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

def collectGlueStamps(board: pcbnew.BOARD) -> List[Tuple[pcbnew.wxPoint, int]]:
    """
    Collect glue stamps from the board. If there are unsupported stamp shapes
    or sizes, raise error. Return list of tuples(position, diameter).
    """
    from pcbnew import ToMM, wxPoint

    stamps: List[Tuple[wxPoint, int]] = []
    errors: List[str] = []

    candidates = board.GetDrawings()
    for f in board.GetFootprints():
        candidates = chain(candidates, f.GraphicalItems())
        # TBA: At the moment, we ignore pads as there is no API. We could
        # read it from a file...
        # for p in f.Pads():
        #     print(type(p.GetPrimitives()))
        #     candidates = chain(candidates, list(p.GetPrimitives()))
    for item in candidates:
        if not isinstance(item, pcbnew.PCB_SHAPE) or item.GetLayer() not in [pcbnew.F_Adhes, pcbnew.B_Adhes]:
            continue
        shape = item.GetShape()
        if shape != pcbnew.SHAPE_T_CIRCLE:
            pos = item.GetStart()
            errors.append(f"Unsupported adhesive shape ({item.ShowShape()}) at ({ToMM(pos[0]), ToMM(pos[1])})")
            continue
        pos = item.GetCenter()
        diameter = 2 * item.GetRadius()
        if diameter not in GLUE_STAMPS.keys():
            errors.append(f"Unsupported glue stamp with diameter {ToMM(diameter)} mm at ({ToMM(pos[0]), ToMM(pos[1])})")
        stamps.append((pos, diameter))
    if len(errors) > 0:
        raise RuntimeError(f"There are unsupported glue shapes on PCB:\n{', '.join(errors)}")
    return stamps

def sortGlueStamps(stamps: List[Tuple[pcbnew.wxPoint, int]]) -> List[Tuple[pcbnew.wxPoint, int]]:
    """
    Given a list of stamp positions and sizes return a new list that sorts them
    in order to minimize travel distance
    """
    from python_tsp.distances import euclidean_distance_matrix # type: ignore
    from python_tsp.heuristics import solve_tsp_local_search   # type: ignore

    distMatrix = euclidean_distance_matrix([x[0] for x in stamps])
    perm, _ = solve_tsp_local_search(distMatrix, list(range(len(stamps))))
    return [stamps[i] for i in perm]

class Manugenerator:
    def __init__(self, project: PrusamanProject, outputdir: Union[str, Path],
                 configuration: Optional[PrusamanConfiguration]=None,
                 requestedConfig: Optional[str]=None,
                 reportInfo: Optional[OutputReporter]= None,
                 reportWarning: Optional[OutputReporter]= None) -> None:
        """
        Construct the object that generates the output. This is an object
        instead of function, so we can implicitly pass reporters and other
        shared resources.

        - project: Prusaman project of the source
        - outputdir: Path to the output directory
        - configuration: you can optionally specify the configuration or the
                         configuration file. If it is not specified, it is
                         deduced from the project.
        - reportInfo: A callback to report logs
        - reportWarning: A callback to report warnings
        """
        self._project: PrusamanProject = project
        self._cfg: PrusamanConfiguration = \
            PrusamanConfiguration.fromProject(project) if configuration is None \
            else configuration
        self._outputdir: Path = Path(outputdir)
        self._requestedConfig = requestedConfig
        self._reportInfo: OutputReporter = defaultTo(reportInfo, stderrReporter)
        self._reportWarning: OutputReporter = defaultTo(reportWarning, stderrReporter)

    def make(self) -> None:
        self._makePanelStage()
        self._makeMillStage()
        self._makeSmtStage()
        self._makeSourcingStage()

    def _makePanelStage(self) -> None:
        panelName = self._fileName("PANEL")
        outdir = self._outputdir / panelName
        outdir.mkdir(parents=True)
        outfile = outdir / (panelName + ".kicad_pcb")

        # Make the panel based on the configuration
        panelCfg = self._cfg["panel"]
        {
            "manual": self._makeManualPanel,
            "kikit": self._makeKikitPanel,
            "script": self._makeScriptPanel
        }[panelCfg["type"]](panelCfg, outfile)

        makeGerbers(source=outfile, outdir=outdir, layers=collectStandardLayers)
        self._makeIbom(source=outfile, outdir=outdir)
        shutil.copyfile(RESOURCES / "datamatrix_znaceni_zbozi_v2.pdf",
                        outdir / "datamatrix_znaceni_zbozi_v2.pdf")
        self._makePanelReadme(outdir, boardPath=outfile)

    def _makeMillStage(self) -> None:
        self._reportInfo("MILL", "Starting MILL stage")
        panelName = self._fileName("PANEL")
        panelPath = self._outputdir / panelName / (panelName + ".kicad_pcb")

        millName = self._fileName("FREZA")
        outdir = self._outputdir / millName
        outdir.mkdir(parents=True, exist_ok=True)
        outfile = outdir / (millName + ".kicad_pcb")

        # Make the gerbers for board that has no features other than cuts
        panel = pcbnew.LoadBoard(str(panelPath))
        preserveOnlyOutline(panel, set(MILL_RELEVANT_FOOTPRINTS))
        pcbnew.SaveBoard(str(outfile), panel)
        makeGerbers(panel, outdir, lambda _: set([pcbnew.Edge_Cuts]))
        self._makeMillReadme(outdir, panel)
        self._reportInfo("MILL", "Mill stage finished")

    def _makeSmtStage(self) -> None:
        self._reportInfo("SMT", "Starting SMT stage")
        smtName = self._fileName("SMT")
        outdir = self._outputdir / smtName
        outdir.mkdir(parents=True, exist_ok=True)

        posName = outdir / (self._project.getName() + "-all-pos.csv")
        bomName = outdir / (self._project.getName() + "-BOM-SMT.csv")
        zipName = outdir / (self._project.getName() + "-BOM-SMT.zip")

        self._makesmtStageDxf(outdir)
        self._makeIbom(self._project.getBoard(), outdir)

        bomFilter = self._bomFilter

        bom = extractComponents(str(self._project.getSchema()))
        checkAnnotation(bom)
        bom = [x for x in bom if bomFilter.assemblyFilter(x)]
        bom.sort(key=naturalComponetKey)

        with open(posName, "w", newline="") as posFile:
            self._makeSmtPosFile(posFile, bom, self._project.getBoard())
        with open(bomName, "w", newline="") as bomFile:
            self._makeSmtBomFile(bomFile, bom)

        zipFiles(zipName, outdir, [posName, bomName])

        panelName = self._fileName("PANEL")
        panelPath = self._outputdir / panelName / (panelName + ".kicad_pcb")

        self._makeGlueStamps(outdir, panelPath)
        self._reportInfo("SMT", "SMT stage finished")

    def _makeSourcingStage(self) -> None:
        self._reportInfo("SOURCING", "Starting sourcing stage")
        sourcingName = self._fileName("NAKUP")
        outdir = self._outputdir / sourcingName
        outdir.mkdir(parents=True, exist_ok=True)

        sourcingListName = outdir / (self._project.getName() + "_BOM.csv")
        newSourcingListName = outdir / (self._project.getName() + "_new_BOM.csv")
        zipName = outdir / (self._project.getName() + "_BOM.zip")

        bomFilter = self._bomFilter

        bom = extractComponents(str(self._project.getSchema()))
        checkAnnotation(bom)
        bom = [x for x in bom if bomFilter.sourcingFilter(x)]

        grouppedBom = groupBy(bom, key=lambda c: (
            getField(c, "ID"),
            getField(c, "Footprint"),
            getField(c, "Value"),
        ))
        groups = list(grouppedBom.values())
        groups.sort(key=lambda g: (getReference(g[0])[:1], len(g)))

        with open(sourcingListName, "w", newline="") as f:
            self._makeSourcingBom(f, groups)

        with open(newSourcingListName, "w", newline="") as f:
            self._makeNewSourcingBom(f, groups, bomFilter)

        zipFiles(zipName, outdir, [sourcingListName])
        self._reportInfo("SOURCING", "Sourcing stage finished")

    def _makeSourcingBom(self, bomFile: TextIO, groups: List[List[Symbol]]) -> None:
        writer = csv.writer(bomFile)
        writer.writerow([
                "Component", "Description", "Part", "References", "Value",
                "Footprint", "Quantity Per PCB", "Datasheet", "req", "ID",
                "part_value", "alt"
            ])
        for i, group in enumerate(groups):
            group.sort(key=naturalComponetKey)
            references = [getField(x, "Reference") for x in group]

            def sameField(fieldName: str) -> str:
                values = [getField(s, fieldName) for s in group]
                if not all(values[0] == x for x in values):
                    self._reportWarning("SOURCING",
                        f"Components {', '.join(references)} should have the same " +
                        f"field {fieldName}, but it differs")
                return defaultTo(values[0], "")

            def nonEmptyField(fieldName: str) -> str:
                for s in group:
                    field = getField(s, fieldName)
                    if field is not None:
                        assert isinstance(field, str)
                        return field
                return ""

            writer.writerow([
                i,
                sameField("Description"),
                sameField("Value"),
                " ".join(references),
                sameField("Value"),
                sameField("Footprint").split(":", 1)[-1],
                len(group),
                nonEmptyField("Datasheet"),
                sameField("req"),
                sameField("ID"),
                sameField("part_value"),
                nonEmptyField("alt")
            ])

    def _makeNewSourcingBom(self, bomFile: TextIO, groups: List[List[Symbol]],
                            bomFilter: BomFilter) -> None:
        writer = csv.writer(bomFile)
        writer.writerow(["Id", "Component", "Quantity per PCB", "Value"])

        for i, group in enumerate(groups):
            if len(group) == 0 or not bomFilter.assemblyFilter(group[0]):
                continue
            writer.writerow([
                getField(group[0], "ID"), i + 1, len(group),
                getField(group[0], "Value")])
        writer.writerow([])
        writer.writerow([])
        for i, group in enumerate(groups):
            if len(group) == 0 or bomFilter.assemblyFilter(group[0]):
                continue
            writer.writerow([
                getField(group[0], "ID"), i + 1, len(group),
                getField(group[0], "Value")])

    def _makeSmtBomFile(self, bomFile: TextIO, bom: List[Symbol]) -> None:
        def required(symbol: Symbol, field: str) -> str:
            v = getField(symbol, field)
            if v is None:
                raise RuntimeError(f"{getReference(symbol)} is missing required field {field}")
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

    def _makeSmtPosFile(self, posFile: TextIO, bom: List[Symbol],
                        boardPath: Path) -> None:
        sourceBoard = pcbnew.LoadBoard(str(boardPath))
        writer = csv.writer(posFile)
        writer.writerow(["Ref", "Val", "Package", "PosX", "PosY", "Rot", "Side"])
        for item in bom:
            ref = getReference(item)

            f = sourceBoard.FindFootprintByReference(getReference(item))
            if f is None:
                self._reportWarning("SMT POS", f"Reference {ref} is present in schematics, " + \
                                    "but not in board. Ignoring.")
            pos = f.GetPosition()
            fpid = f.GetFPID()
            writer.writerow([
                f.GetReference(),
                f.GetValue(),
                fpid.GetUniStringLibItemName(),
                pcbnew.ToMM(pos[0]),
                pcbnew.ToMM(pos[1]),
                f.GetOrientation() / 10,
                layerToSide(f.GetLayer())
            ])

    def _makeMillReadme(self, outdir: Path, panel: pcbnew.BOARD) -> None:
        try:
            with open(self._project.getMillReadmeTemplate(), "r") as f:
                content = populateText(f.read(), panel, self._cfg["board_id"])
        except FileNotFoundError as e:
            raise RuntimeError(f"Missing mill readme template. Please create the file {self._project.getMillReadmeTemplate()}") from None
        with open(outdir / "README.txt", "w") as f:
            f.write(content)

    def _makeGlueStamps(self, outdir: Path, panelPath: Path) -> None:
        panel = pcbnew.LoadBoard(str(panelPath))
        glueStamps = collectGlueStamps(panel)
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

    def _makePanelReadme(self, outdir: Path, boardPath: Path) -> None:
        try:
            with open(self._project.getPanelReadmeTemplate(), "r") as f:
                content = populateText(f.read(), pcbnew.LoadBoard(str(boardPath)), self._cfg["board_id"])
        except FileNotFoundError as e:
            raise RuntimeError(f"Missing panel readme template. Please create the file {self._project.getPanelReadmeTemplate()}") from None
        with open(outdir / "README.txt", "w") as f:
            f.write(content)

    def _fileName(self, prefix: str) -> str:
        return f"{prefix}-{self._project.getName()}"

    def _makeManualPanel(self, cfg: Dict[str, Any], output: Path) -> None:
        try:
            shutil.copyfile(cfg["source"], output)
        except FileNotFoundError:
            raise RuntimeError(f"Cannot copy {cfg['source']} into final destination")

    def _makeKikitPanel(self, cfg: Dict[str, Any], output: Path) -> None:
        self._reportInfo("KIKIT", "Starting panel")
        from kikit import panelize_ui_impl as ki  # type: ignore
        from kikit.panelize_ui import doPanelization  # type: ignore

        cfgFile = self._project.getDir() / cfg["configuration"]

        os.environ["PRUSAMAN_SOURCE_PROJECT"] = str(self._project.getDir())

        input = self._project.getBoard()
        preset = ki.obtainPreset([str(cfgFile)])
        doPanelization(str(input), str(output), preset)
        self._reportInfo("KIKIT", "Panel finished")


    def _makeScriptPanel(self, cfg: Dict[str, Any], output: Path) -> None:
        command = [cfg["script"], str(self._project.getBoard()), str(output)]
        result = subprocess.run(command, capture_output=True)
        stdout = result.stdout.decode("utf-8")
        stderr = result.stderr.decode("utf-8")
        if result.returncode != 0:
            message = f"The script for building panel {cfg['script']} failed " + \
                      f"with code {result.returncode} and output:\n{stdout}\n{stderr}"
            raise RuntimeError(message)
        self._reportInfo("PANEL_SCRIPT", stdout)
        self._reportWarning("PANEL_SCRIPT", stderr)

    def _makeIbom(self, source: Path, outdir: Path) -> None:
        with NamedTemporaryFile(mode="w", prefix="ibomnet_", suffix=".net",
                                delete=False) as f:
            try:
                bom = extractComponents(str(self._project.getSchema()))
                exportIBomNetlist(f, bom)
                f.close()

                ibomBinary = RESOURCES / "ibom" / "InteractiveHtmlBom" / "generate_interactive_bom.py"
                command = [locatePythonInterpreter(), str(ibomBinary), "--no-browser",
                        "--dark-mode", "--extra-fields", "ID,PnB",
                        "--name-format", "%f-ibom",
                        "--netlist-file", f.name,
                        "--dest-dir", str(outdir), str(source)]
                result = subprocess.run(command, capture_output=True)
                stdout = result.stdout.decode("utf-8")
                stderr = result.stderr.decode("utf-8")
                if result.returncode != 0:
                    message = f"Ibom generation of {source} failed " + \
                            f"with code {result.returncode} and output:\n{stdout}\n{stderr}"
                    raise RuntimeError(message)
                self._reportInfo("IBOM", stdout)
                self._reportWarning("IBOM", stderr)
            finally:
                f.close()
                os.unlink(f.name)

    def _commonBomFilter(self, item: Symbol) -> bool:
        ref = getReference(item)
        if any(ref.startswith(pref) for pref in ["#", "M", "NT", "G"]):
            return False
        return True

    def _legacyBomAssemblyFilter(self, item: Symbol) -> bool:
        """
        Realize legacy BOM filter for assembly - i.e., start marks "do not fit"
        """
        id = defaultTo(getField(item, "id"), "")
        if id == "":
            raise RuntimeError(f"Symbol {getReference(item)} has empty ID - cannot proceed")
        return self._commonBomFilter(item) and id != "" and ("*" not in id)

    def _legacyBomSourcingFilter(self, item: Symbol) -> bool:
        """
        Realize legacy BOM filter for sourcing - i.e., source everything except
        parts marked with "*"
        """
        id = defaultTo(getField(item, "id"), "")
        if id == "":
            raise RuntimeError(f"Symbol {getReference(item)} has empty ID - cannot proceed")
        return self._commonBomFilter(item) and id != "*"

    def _iBomFilter(self, item: Symbol) -> bool:
        config = defaultTo(getField(item, "Config"), "")
        configs = [x.strip() for x in config.split(" ") if x.strip() != ""]

        allow = len(configs) == 0 or f"+{self._requestedConfig}" in configs
        return allow and self._commonBomFilter(item)

    @property
    def _bomFilter(self) -> BomFilter:
        filters: Dict[str, Callable[[], BomFilter]] = {
            "legacy": lambda: LegacyFilter(),
            "pnb": lambda: PnBFilter(),
        }
        return filters[self._cfg["bom_filter"]]()
