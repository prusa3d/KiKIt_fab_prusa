from zipfile import ZipFile, ZIP_DEFLATED
from pathlib import Path
import shutil
import os
import sys

from typing import Union, List, Optional, TypeVar, Callable, Tuple, Iterable, Dict

T = TypeVar("T")
K = TypeVar("K")

StrPath = Union[Path, str]

def replaceDirectory(target: Union[Path, str], source: Union[Path, str]) -> None:
    if not os.path.exists(source):
        return
    try:
        os.replace(source, target)
        return
    except Exception:
        pass
    shutil.rmtree(target, ignore_errors=True)
    shutil.move(source, target)

def zipFiles(archivePath: StrPath, basePath: StrPath, archiveSubdir: Optional[StrPath],
             files: List[StrPath]) -> None:
    """
    Take archive output name, base path and list of files to put inside a ZIP
    archive. If the archive exists, the files are added to the existing archive.
    """
    assert os.path.realpath(archivePath) not in [os.path.realpath(f) for f in files]
    with ZipFile(archivePath, "a", compression=ZIP_DEFLATED, compresslevel=9) as zipF:
        for fileName in files:
            relativeName = os.path.relpath(str(fileName), str(basePath))
            if archiveSubdir is not None:
                relativeName = os.path.join(archiveSubdir, relativeName)
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
