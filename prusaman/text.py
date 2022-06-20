from decimal import Decimal
from typing import Optional, Callable, Union
import pcbnew # type: ignore
from .pcbnew_common import findBoardBoundingBox
from .params import RESOURCES
from datetime import datetime
from kikit.text import Formatter
from kikit.sexpr import findNode, readStrDict, parseSexprF, isElement

def formatBoardSize(board: Optional[pcbnew.BOARD]) -> str:
    if board is None:
        raise RuntimeError("Cannot use board size in template without board context")
    bbox = findBoardBoundingBox(board)
    return f"{pcbnew.ToMM(bbox.GetWidth())}×{pcbnew.ToMM((bbox.GetHeight()))} mm"

def dmcLayername(side: pcbnew.LAYER):
    if side == pcbnew.F_Cu:
        return "top"
    if side == pcbnew.B_Cu:
        return "bottom"
    raise RuntimeError("Bug, please report: Unsupported DMC layer")

def formatDatamatrixInfo(board: Optional[pcbnew.BOARD], boardId: Union[str, int, None]) -> str:
    if board is None:
        raise RuntimeError("Cannot use DMC in template without board context")
    if boardId is None:
        raise RuntimeError("Cannot use DMC in template without project context")
    dmcs = [f for f in board.Footprints()
            if f.GetValue().startswith("G_DATAMATRIX")]
    dmcs.sort(key=lambda f: (f.GetLayer(), f.GetPosition()[0], -f.GetPosition()[1]))
    message = "- More about data format in attached PDF document\n"
    message += f"- ID {boardId}\n"
    message += f"- DMC positions:\n"
    for d in dmcs:
        message += f"    - \"{d.GetReference()}\", {pcbnew.ToMM(d.GetPosition()[0])}, {pcbnew.ToMM(-d.GetPosition()[1])}, {d.GetOrientation() // 10}, {dmcLayername(d.GetLayer())}\n"
    return message

def formatStackup(board: Optional[pcbnew.BOARD]) -> str:
    if board is None:
        raise RuntimeError("Cannot use stackup in template without board context")
    with open(board.GetFileName()) as f:
        bAst = parseSexprF(f, 20) # We use limit to speed up the parsing
    setup = findNode(bAst.items, "setup")
    if setup is None:
        raise RuntimeError("The board doesn't contain stackup information")
    stackup = findNode(setup.items, "stackup")
    if stackup is None:
        raise RuntimeError("The board doesn't contain stackup information")
    layersText = []
    thickness = Decimal(0)
    for layerInfo in stackup.items[1:]:
        if not isElement("layer")(layerInfo):
            continue
        kicadLayerName = layerInfo.items[1].value
        if kicadLayerName in ["F.Paste", "B.Paste"]:
            continue

        properties = readStrDict(layerInfo.items[2:])
        paramTexts = [f"{k}: {v}" for k, v in properties.items() if k != "type"]

        text = properties["type"]
        if len(paramTexts) > 0:
            text += " (" + ", ".join(paramTexts) + ")"
        if not kicadLayerName.startswith("dielectric"):
            text += f" represented by layer {kicadLayerName}"
        layersText.append(text)

        thickness += Decimal(properties.get("thickness", 0))
    return "\n".join([f"- {x}" for x in layersText]) + f"\n\nBoard thickness {thickness:.2g} mm"

def formatMinimalDrilling(board: Optional[pcbnew.BOARD]) -> str:
    if board is None:
        raise RuntimeError("Cannot use minDrill in template without board context")
    mDrill = board.GetDesignSettings().m_MinThroughDrill
    return f"{pcbnew.ToMM(mDrill)}mm"

def formatMinimalSpacing(board: Optional[pcbnew.BOARD]) -> str:
    if board is None:
        raise RuntimeError("Cannot use minSpace in template without board context")
    spacing = board.GetDesignSettings().m_MinClearance
    return f"{pcbnew.ToMM(spacing)}mm"

def formatMinimalWidth(board: Optional[pcbnew.BOARD]) -> str:
    if board is None:
        raise RuntimeError("Cannot use minTrace in template without board context")
    width = board.GetDesignSettings().m_TrackMinWidth
    return f"{pcbnew.ToMM(width)}mm"

def populateText(template: str, board: Optional[pcbnew.BOARD]=None,
                 boardId: Union[str, int, None]=None) -> str:
    """
    Expands common variables in the text
    """
    attribs = {
        "size": Formatter(lambda: formatBoardSize(board)),
        "dmc": Formatter(lambda: formatDatamatrixInfo(board, boardId)),
        "date": Formatter(lambda: datetime.today().strftime("%Y-%m-%d")),
        "boardTitle": Formatter(lambda: board.GetTitleBlock().GetTitle()),
        "boardDate": Formatter(lambda: board.GetTitleBlock().GetDate()),
        "boardRevision": Formatter(lambda: board.GetTitleBlock().GetRevision()),
        "boardCompany": Formatter(lambda: board.GetTitleBlock().GetCompany()),
        "stackup": Formatter(lambda: formatStackup(board)),
        "minDrill": Formatter(lambda: formatMinimalSpacing(board)),
        "minSpace": Formatter(lambda: formatMinimalSpacing(board)),
        "minTrace": Formatter(lambda: formatMinimalWidth(board))
    }

    for i in range(10):
        attribs[f"boardComment{i + 1}"] = Formatter(lambda: board.GetTitleBlock().GetComment(i))

    try:
        return template.format(**attribs)
    except KeyError as e:
        raise RuntimeError(f"Unknown variable {e} in text:\n{template}") from None
