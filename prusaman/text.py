from typing import Optional, Callable
import pcbnew # type: ignore
from .pcbnew_common import findBoardBoundingBox
from .params import RESOURCES
from datetime import datetime

class Formatter:
    def __init__(self, fn: Callable[[], str]) -> None:
        self.fn = fn
        self.value: Optional[str] = None

    def __str__(self) -> str:
        if self.value is None:
            self.value = self.fn()
        return self.value

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
