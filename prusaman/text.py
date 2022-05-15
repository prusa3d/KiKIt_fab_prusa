from typing import Optional, Callable, Union
import pcbnew # type: ignore
from .pcbnew_common import findBoardBoundingBox
from .params import RESOURCES
from datetime import datetime
from kikit.text import Formatter

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
        "boardCompany": Formatter(lambda: board.GetTitleBlock().GetCompany())
    }

    for i in range(10):
        attribs[f"boardComment{i + 1}"] = Formatter(lambda: board.GetTitleBlock().GetComment(i))

    try:
        return template.format(**attribs)
    except KeyError as e:
        raise RuntimeError(f"Unknown variable {e} in text:\n{template}") from None
