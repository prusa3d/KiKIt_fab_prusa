from __future__ import annotations

from typing import Callable, TypeVar, Optional, Dict, Union, Any, List
import os
import sys
from pathlib import Path
from ruamel.yaml import YAML
from ruamel.yaml.parser import ParserError
import textwrap
import shutil
import json
from tempfile import TemporaryDirectory
import schema # type: ignore
import subprocess
import pcbnew # type: ignore
from .pcbnew_common import findBoardBoundingBox
from datetime import datetime
from io import StringIO

PKG_BASE = Path(__file__).resolve().parent
RESOURCES = Path(PKG_BASE) / "resources"

T = TypeVar('T')
OutputReporter = Callable[[str, str], None]  # Takes TAG and message

def stderrReporter(tag: str, message: str) -> None:
    sys.stderr.write(f"{tag}: {message}\n")

def defaultTo(val: Optional[T], default: T) -> T:
    if val is None:
        return default
    return val

class Choice:
    def __init__(self, allowed: List[Any]) -> None:
        self.allowed: List[Any] = allowed

    def validate(self, data: Any) -> Any:
        if data in self.allowed:
            return data
        raise schema.SchemaError(f"'{data}' is not one of allowed: {', '.join(self.allowed)}")

class IsKiCADBoard:
    def __init__(self, exists: bool=False):
        self.exists = exists

    def validate(self, data: Any) -> str:
        if not isinstance(data, str):
            raise schema.SchemaError(f"KiCAD board file is not string; got {data}")
        if not data.endswith(".kicad_pcb"):
            raise schema.SchemaError(f"Extension of board file must be '.kicad_pcb'")
        if self.exists and not os.path.exists(data):
            raise schema.SchemaError(f"'{data} doesn't exists")
        return data

class Formatter:
    def __init__(self, fn: Callable[[], str]) -> None:
        self.fn = fn
        self.value: Optional[str] = None

    def __str__(self) -> str:
        if self.value is None:
            self.value = self.fn()
        return self.value


def replaceDirectory(target: Union[Path, str], source: Union[Path, str]) -> None:
    shutil.rmtree(target)
    os.rename(source, target)

def formatBoardSize(board: Optional[pcbnew.BOARD]) -> str:
    if board is None:
        raise RuntimeError("Cannot use board size in template without board context")
    bbox = findBoardBoundingBox(board)
    return f"{pcbnew.ToMM(bbox.GetWidth())}×{pcbnew.ToMM((bbox.GetHeight()))} mm"

def formatDatamatrixInfo(board: Optional[pcbnew.BOARD]) -> str:
    if board is None:
        raise RuntimeError("Cannot use DCM in template without board context")
    return "TBA: There will be DCM info"


def populateText(template: str, board: Optional[pcbnew.BOARD]) -> str:
    """
    Expands common variables in the text
    """
    attribs = {
        "size": Formatter(lambda: formatBoardSize(board)),
        "dcm": Formatter(lambda: formatDatamatrixInfo(board)),
        "date": Formatter(lambda: datetime.today().strftime("%Y-%m-%d")),
        "prusaman_scripts": str(RESOURCES / "kikitscripts")
    }
    return template.format(**attribs)


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

class PrusamanProject:
    """
    This code represents a KiCAD project and allows easy access to individual
    files without the need to hassle with project names.
    """
    def __init__(self, path: str) -> None:
        self._projectdir: Path = Path(path).resolve()
        name = None
        if path.endswith(".kicad_pro"):
            name = self._projectdir.name[:-len(".kicad_pro")]
            self._projectdir = self._projectdir.parent
        else:
            if not self._projectdir.is_dir():
                raise RuntimeError(f"The project directory {self._projectdir} is not a directory")
            name = self._resolveProjectName(self._projectdir)
        self._name: str = name

    @staticmethod
    def _resolveProjectName(path: Path) -> str:
        candidate: Optional[str] = None
        for item in path.iterdir():
            if not item.name.endswith(".kicad_pro"):
                continue
            if candidate is not None:
                raise RuntimeError(f"There are multiple projects ({candidate} " +
                                   f"and {item.name}) in directory {path}. Not " +
                                   f"clear which one to choose.")
            candidate = item.name
        if candidate is not None:
            return candidate[:-len(".kicad_pro")]
        raise RuntimeError(f"No project found in {path}")

    def getConfiguration(self) -> Path:
        return self._projectdir / "prusaman.yaml"

    def getProject(self) -> Path:
        return self._projectdir / f"{self._name}.kicad_pro"

    def getBoard(self) -> Path:
        return self._projectdir / f"{self._name}.kicad_pcb"

    def getSchema(self) -> Path:
        return self._projectdir / f"{self._name}.kicad_sch"

    def getName(self) -> str:
        return self._name

    def getPanelReadmeTemplate(self) -> Path:
        return self._projectdir / "readme.panel.template.txt"


class PrusamanConfiguration:
    def __init__(self, configuration: Dict[str, Any]) -> None:
        self.cfg: Dict[str, Any] = configuration
        try:
            self._buildSchema().validate(self.cfg)
        except schema.SchemaError as e:
            raise RuntimeError(str(e)) from None

    @classmethod
    def fromFile(cls, path: Union[str, Path]) -> PrusamanConfiguration:
        try:
            yaml = YAML(typ='safe')
            with open(path, "r") as f:
                content = f.read()
            # Expand variables used in the configuration
            content = populateText(content, None)
            cfg = yaml.load(StringIO(content))
            return cls(cfg)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Configuration file {path} doesn't exist.") from None
        except ParserError as e:
            parserMessage = str(e)
            parserMessage = parserMessage.replace(str(path), Path(path).name)
            raise RuntimeError(
                f"Invalid syntax of source file {path}:\n{textwrap.indent(parserMessage, '    ')}") from None

    @classmethod
    def fromProject(cls, project: PrusamanProject) -> PrusamanConfiguration:
        return PrusamanConfiguration.fromFile(project.getConfiguration())

    @staticmethod
    def _buildSchema() -> schema.Schema:
        from schema import Schema, And, Or
        manualPanel = {
            "type": "manual",
            "source": IsKiCADBoard(exists=True)
        }
        scriptPanel = {
            "type": "script",
            "script": "script"
        }
        kikitPanel = {
            "type": "kikit",
            "configuration": dict
        }
        panelSchema = And(
            {
                "type": Choice(["manual", "script", "kikit"]),
                str: object
            },
            Or(manualPanel, scriptPanel, kikitPanel))

        return Schema({
            "revision": And(int, lambda x: x > 0),
            "board_id": Or(str, int),
            "panel": panelSchema
        })

    def getPanelization(self) -> Dict[str, Any]:
        cfg = self.cfg["panel"]
        assert isinstance(cfg, dict)
        return cfg


class Manugenerator:
    def __init__(self, source: PrusamanProject, outputdir: Union[str, Path],
                 configuration: Optional[PrusamanConfiguration]=None,
                 reportInfo: Optional[OutputReporter]= None,
                 reportWarning: Optional[OutputReporter]= None) -> None:
        """
        Construct the object that generates the output. This is an object
        instead of function, so we can implicitly pass reporters and other
        shared resources.

        - source: Prusaman project of the source
        - outputdir: Path to the output directory
        - configuration: you can optionally specify the configuration or the
                         configuration file. If it is not specified, it is
                         deduced from the project.
        - reportInfo: A callback to report logs
        - reportWarning: A callback to report warnings
        """
        self._source: PrusamanProject = source
        self._cfg: PrusamanConfiguration = \
            PrusamanConfiguration.fromProject(source) if configuration is None \
            else configuration
        self._outputdir: Path = Path(outputdir)
        self._reportInfo: OutputReporter = defaultTo(reportInfo, stderrReporter)
        self._reportWarning: OutputReporter = defaultTo(reportWarning, stderrReporter)

    def make(self) -> None:
        self._makePanelStage()
        self._makeMillStage()

    def _makePanelStage(self) -> None:
        panelName = self._fileName("PANEL")
        outdir = self._outputdir / panelName
        outdir.mkdir(parents=True)
        outfile = outdir / (panelName + ".kicad_pcb")

        # Make the panel based on the configuration
        panelCfg = self._cfg.getPanelization()
        {
            "manual": self._makeManualPanel,
            "kikit": self._makeKikitPanel,
            "script": self._makeScriptPanel
        }[panelCfg["type"]](panelCfg, outfile)


        self._makeGerbers(source=outfile, outdir=outdir, layers=collectStandardLayers)
        self._makeIbom(source=outfile, outdir=outdir)
        shutil.copyfile(RESOURCES / "datamatrix_znaceni_zbozi_v2.pdf", outdir / "datamatrix_znaceni_zbozi_v2.pdf")
        self._makePanelReadme(outdir, boardPath=outfile)

    def _makeMillStage(self) -> None:
        panelName = self._fileName("PANEL")
        panelPath = self._outputdir / panelName / (panelName + ".kicad_pcb")

        millName = self._fileName("FREZA")
        outdir = self._outputdir / millName
        outdir.mkdir(parents=True)
        outfile = outdir / (millName + ".kicad_pcb")

        panel = pcbnew.LoadBoard(str(panelPath))
        preserveOnlyOutline(panel, set([
            "prusa_other:hole4cutter-1,5mm",
            "prusa_other:hole4cutter-2mm"]))
        pcbnew.SaveBoard(str(outfile), panel)
        self._makeGerbers(panel, outdir, lambda _: set([pcbnew.Edge_Cuts]))

        renderHolesToEdges(panel)
        self._makeDxf(panel, outdir, lambda _: set([pcbnew.Edge_Cuts]))
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
        with open(self._source.getPanelReadmeTemplate(), "r") as f:
            content = populateText(f.read(), pcbnew.LoadBoard(str(boardPath)))
        with open(outdir / "README.txt", "w") as f:
            f.write(content)

    def _fileName(self, prefix: str) -> str:
        return f"{prefix}-{self._source.getName()}"

    def _makeManualPanel(self, cfg: Dict[str, Any], output: Path) -> None:
        try:
            shutil.copyfile(cfg["source"], output)
        except FileNotFoundError:
            raise RuntimeError(f"Cannot copy {cfg['source']} into final destination")

    def _makeKikitPanel(self, cfg: Dict[str, Any], output: Path) -> None:
        from kikit.panelize_ui import doPanelization # type: ignore
        from kikit import panelize_ui_impl as ki # type: ignore
        kikitCfg = cfg["configuration"]
        input = self._source.getBoard()

        with TemporaryDirectory() as tmpdir:
            kikitCfgFile = Path(tmpdir) / "configuration.json"
            with open(kikitCfgFile, "w") as f:
                json.dump(kikitCfg, f)

            os.environ["PRUSAMAN_PRUSA_LIB"] = str(RESOURCES / "prusalib")

            preset = ki.obtainPreset([str(kikitCfgFile)])
            doPanelization(str(input), str(output), preset)


    def _makeScriptPanel(self, cfg: Dict[str, Any], output: Path) -> None:
        command = [cfg["script"], str(self._source.getBoard()), str(output)]
        result = subprocess.run(command, capture_output=True)
        stdout = result.stdout.decode("utf-8")
        stderr = result.stderr.decode("utf-8")
        if result.returncode != 0:
            message = f"The script for building panel {cfg['script']} failed " + \
                      f"with code {result.returncode} and output:\n{stdout}\n{stderr}"
            raise RuntimeError(message)
        self._reportInfo("PANEL_SCRIPT", stdout)
        self._reportWarning("PANEL_SCRIPT", stderr)

    def _makeGerbers(self, source: Union[Path, pcbnew.Board], outdir: Path,
                    layers: Callable[[pcbnew.BOARD], set[int]]) -> None:
        if isinstance(source, pcbnew.BOARD):
            board = source
        else:
            board = pcbnew.LoadBoard(str(source))

        gerberSubdir = outdir / "gerber"

        pctl = pcbnew.PLOT_CONTROLLER(board)
        popt = pctl.GetPlotOptions()
        popt.SetOutputDirectory(str(gerberSubdir))
        popt.SetPlotFrameRef(False)
        popt.SetSketchPadLineWidth(pcbnew.FromMM(0.1))
        popt.SetUseGerberAttributes(False)
        popt.SetIncludeGerberNetlistInfo(True)
        popt.SetCreateGerberJobFile(True)
        popt.SetUseGerberProtelExtensions(True)
        popt.SetExcludeEdgeLayer(True)
        popt.SetScale(1)
        popt.SetUseAuxOrigin(True)
        popt.SetUseGerberX2format(False)
        popt.SetSubtractMaskFromSilk(True)
        popt.SetSkipPlotNPTH_Pads(False)

        try:
            for layer in layers(board):
                pctl.SetLayer(layer)
                pctl.OpenPlotfile(pcbnew.LayerName(layer), pcbnew.PLOT_FORMAT_GERBER, "")
                if not pctl.PlotLayer():
                    raise RuntimeError(f"Cannot plot layer {pcbnew.LayerName(layer)}")
        finally:
            pctl.ClosePlot()

        drlwriter = pcbnew.EXCELLON_WRITER(board)
        drlwriter.SetOptions(
            aMirror=False,
            aMinimalHeader=True,
            aOffset=pcbnew.wxPoint(0, 0),
            aMerge_PTH_NPTH=True)
        drlwriter.SetRouteModeForOvalHoles(False)

        # Set metric format
        drlwriter.SetFormat(True, pcbnew.GENDRILL_WRITER_BASE.DECIMAL_FORMAT)
        drlwriter.CreateDrillandMapFilesSet(str(gerberSubdir), aGenDrill=True, aGenMap=False)

        shutil.make_archive(str(outdir / "gerber"), "zip", str(gerberSubdir))

    def _makeDxf(self, source: Union[Path, pcbnew.Board], outdir: Path,
                 layers: Callable[[pcbnew.BOARD], set[int]]) -> None:
        if isinstance(source, pcbnew.BOARD):
            board = source
        else:
            board = pcbnew.LoadBoard(str(source))

        pctl = pcbnew.PLOT_CONTROLLER(board)
        popt = pctl.GetPlotOptions()
        popt.SetOutputDirectory(str(outdir))
        popt.SetAutoScale(False)
        popt.SetScale(1)
        popt.SetMirror(False)
        popt.SetExcludeEdgeLayer(True)
        popt.SetScale(1)
        popt.SetDXFPlotUnits(pcbnew.DXF_UNITS_MILLIMETERS)
        popt.SetDXFPlotPolygonMode(False)

        try:
            for layer in layers(board):
                pctl.SetLayer(layer)
                pctl.OpenPlotfile(pcbnew.LayerName(layer), pcbnew.PLOT_FORMAT_DXF, "")
                if not pctl.PlotLayer():
                    raise RuntimeError(f"Cannot plot layer {pcbnew.LayerName(layer)}")
        finally:
            pctl.ClosePlot()


    def _makeIbom(self, source: Path, outdir: Path) -> None:
        ibomBinary = RESOURCES / "ibom" / "InteractiveHtmlBom" / "generate_interactive_bom.py"
        command = [str(ibomBinary), "--no-browser",
                   "--name-format", "%f-ibom",
                   "--dest-dir", str(outdir), str(source)]
        result = subprocess.run(command, capture_output=True)
        stdout = result.stdout.decode("utf-8")
        stderr = result.stderr.decode("utf-8")
        if result.returncode != 0:
            message = f"Ibom generation of {source} failed " + \
                      f"with code {result.returncode} and output:\n{stdout}\n{stderr}"
            raise RuntimeError(message)
        self._reportInfo("PANEL_IBOM", stdout)
        self._reportWarning("PANEL_IBOM", stderr)

