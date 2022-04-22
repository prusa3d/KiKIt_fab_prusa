from zipfile import ZipFile
from pathlib import Path
import shutil
import os
import sys

from typing import Union, List, Optional, TypeVar, Callable, Tuple, Iterable, Dict

T = TypeVar("T")
K = TypeVar("K")

StrPath = Union[Path, str]

def zipFiles(archivePath: StrPath, basePath: StrPath, files: List[StrPath]) -> None:
    """
    Take archive output name, base path and list of files to put inside a ZIP
    archive
    """
    assert os.path.realpath(archivePath) not in [os.path.realpath(f) for f in files]
    with ZipFile(archivePath, "w") as zipF:
        for fileName in files:
            relativeName = os.path.relpath(str(fileName), str(basePath))
            with open(fileName, "rb") as src, zipF.open(str(relativeName), "w") as dst:
                shutil.copyfileobj(src, dst)

def defaultTo(val: Optional[T], default: T) -> T:
    """
    Return value or default if provided value is None
    """
    if val is None:
        return default
    return val


def splitOn(input: str, predicate: Callable[[str], bool]) \
        -> Tuple[str, str]:
    """
    Split a string into a head fullfilling predicate and the rest
    """
    left = ""
    for i, x in enumerate(input):
        if predicate(x):
            left += x
        else:
            break
    return left, input[i:]

def groupBy(items: Iterable[T], key: Callable[[T], K]) -> Dict[K, List[T]]:
    """
    Split list into groups
    """
    result: Dict[K, List[T]] = {}
    for item in items:
        itemKey = key(item)
        group = result.get(itemKey, [])
        group.append(item)
        result[itemKey] = group
    return result

def locatePythonInterpreter() -> str:
    """
    Locate Python interpreter that belongs to the KiCAD's installation
    """
    e = Path(sys.executable)
    if e.name in ["kicad.exe", "pcbnew.exe"]:
        e = e.parent / "pythonw.exe"
    return str(e)
