import shutil
from pathlib import Path
from typing import Callable, Set, Union

from pcbnew import (BOARD, DXF_UNITS_MILLIMETERS,  # type: ignore
                    EXCELLON_WRITER, GENDRILL_WRITER_BASE, PLOT_CONTROLLER,
                    PLOT_FORMAT_DXF, PLOT_FORMAT_GERBER, FromMM, LayerName,
                    LoadBoard, wxPoint)


def makeGerbers(source: Union[Path, BOARD], outdir: Path,
                layers: Callable[[BOARD], Set[int]]) -> None:
    if isinstance(source, BOARD):
        board = source
    else:
        board = LoadBoard(str(source))

    pctl = PLOT_CONTROLLER(board)
    popt = pctl.GetPlotOptions()
    popt.SetOutputDirectory(str(outdir))
    popt.SetPlotFrameRef(False)
    popt.SetSketchPadLineWidth(FromMM(0.1))
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
    popt.SetDisableGerberMacros(True)

    try:
        for layer in layers(board):
            pctl.SetLayer(layer)
            pctl.OpenPlotfile(LayerName(layer), PLOT_FORMAT_GERBER, "")
            if not pctl.PlotLayer():
                raise RuntimeError(f"Cannot plot layer {LayerName(layer)}")
    finally:
        pctl.ClosePlot()

    drlwriter = EXCELLON_WRITER(board)
    drlwriter.SetOptions(
        aMirror=False,
        aMinimalHeader=True,
        aOffset=wxPoint(0, 0),
        aMerge_PTH_NPTH=True)
    drlwriter.SetRouteModeForOvalHoles(False)

    # Set metric format
    drlwriter.SetFormat(True, GENDRILL_WRITER_BASE.DECIMAL_FORMAT)
    drlwriter.CreateDrillandMapFilesSet(str(outdir), aGenDrill=True, aGenMap=False)

    # shutil.make_archive(str(outdir / "gerber"), "zip", str(gerberSubdir))

def makeDxf(source: Union[Path, BOARD], outdir: Path,
            layers: Callable[[BOARD], Set[int]]) -> None:
    if isinstance(source, BOARD):
        board = source
    else:
        board = LoadBoard(str(source))

    pctl = PLOT_CONTROLLER(board)
    popt = pctl.GetPlotOptions()
    popt.SetOutputDirectory(str(outdir))
    popt.SetAutoScale(False)
    popt.SetScale(1)
    popt.SetMirror(False)
    popt.SetExcludeEdgeLayer(True)
    popt.SetScale(1)
    popt.SetDXFPlotUnits(DXF_UNITS_MILLIMETERS)
    popt.SetDXFPlotPolygonMode(False)

    try:
        for layer in layers(board):
            pctl.SetLayer(layer)
            pctl.OpenPlotfile(LayerName(layer), PLOT_FORMAT_DXF, "")
            if not pctl.PlotLayer():
                raise RuntimeError(f"Cannot plot layer {LayerName(layer)}")
    finally:
        pctl.ClosePlot()
