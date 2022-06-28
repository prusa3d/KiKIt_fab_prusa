import re
import shutil
from typing import Dict, List, Union, Optional
from pathlib import Path
from urllib.request import urlopen, Request
from zipfile import ZipFile
import pcbnew
from itertools import zip_longest
from kikit.sexpr import isElement, parseSexprS, SExpr, Atom

from .params import FOOTPRINT_REPO
from .util import replaceDirectory

class PrusaFootprints:
    """
    This class represents a footprint library fetched from Github. The library
    is stored on disk and you can retrieve footprints from it and you can update
    it.
    """
    def __init__(self, accessToken: str, repo: Optional[str]=None,
                 path: Union[None, Path, str]=None) -> None:
        self._accessToken = accessToken
        self._repo = repo if repo is not None else FOOTPRINT_REPO
        self._path = self._defaultPath() if path is None else Path(path)

        self._path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _defaultPath() -> Path:
        """
        Finds the most suitable path to store the library
        """
        return Path.home() / ".prusaman" / "footprints"

    @property
    def _libLoc(self) -> Path:
        return self._path / "lib"

    @property
    def _revisionLoc(self) -> Path:
        return self._path / "revision.txt"

    def _makeGhRequest(self, url, data=None, headers=None, origin_req_host=None,
                       unverifiable=False, method=None):
        if headers is None:
            headers = {}
        headers["Authorization"] = f"token {self._accessToken}"
        if "Accept" not in headers:
            headers["Accept"] = "application/vnd.github.v3+json"
        return urlopen(Request(url, data, headers, origin_req_host, unverifiable, method))

    def getLocalRevision(self) -> Optional[str]:
        try:
            with open(self._revisionLoc) as f:
                return f.read().strip()
        except Exception:
            return None

    def getRemoteRevision(self) -> str:
        headers = {
            "Accept": "application/vnd.github.VERSION.sha"
        }
        with self._makeGhRequest(
                f"https://api.github.com/repos/{self._repo}/commits/master",
                headers=headers) as f:
            return f.read().decode("utf-8").strip()

    def updateFromRemote(self) -> None:
        tempLoc = self._path / "lib-tmp"
        tempZip = self._path / "lib.zip"
        shutil.rmtree(tempLoc, ignore_errors=True)
        tempZip.unlink(missing_ok=True)

        with self._makeGhRequest(f"https://api.github.com/repos/{self._repo}/zipball/master") as resp:
            with open(tempZip, "wb") as f:
                shutil.copyfileobj(resp, f)
        with ZipFile(tempZip, mode="r") as archive:
            archive.extractall(tempLoc)
        revisionDir = next(tempLoc.iterdir())
        for x in revisionDir.iterdir():
            shutil.move(str(x), str(tempLoc))
        revisionDir.rmdir()

        replaceDirectory(self._libLoc, tempLoc)

        revision = revisionDir.name.split("-")[-1]
        with open(self._revisionLoc, "w") as f:
            f.write(revision.strip())

    def getFootprint(self, libname: str, fname: str) -> Optional[pcbnew.FOOTPRINT]:
        libPath = self._libLoc / "prusa-footprints" / f"{libname}.pretty"
        if not (libPath / f"{fname}.kicad_mod").exists():
            return None
        return pcbnew.FootprintLoad(str(libPath), str(fname))

def extractRevision(footprint: pcbnew.FOOTPRINT) -> Optional[str]:
    for x in footprint.GraphicalItems():
        if not isinstance(x, pcbnew.FP_TEXT):
            continue
        text = x.GetText()
        if text.startswith("PRUSA_REVISION:"):
            return text.replace("PRUSA_REVISION: ", "")
    return None

def matchesFootprintPattern(footprint: pcbnew.FOOTPRINT,
                            pattern: pcbnew.FOOTPRINT,
                            workingDir: Path) -> bool:
    """
    There is no equality implemented in KiCAD between footprints. Let's decide
    the equality by saving footprints, stripping timestamps and sorting it. It's
    less laborious than manually walking the tree and probably more reliable.
    """
    pattern.SetPosition(footprint.GetPosition())
    pattern.SetOrientation(footprint.GetOrientation())

    fId = footprint.GetFPID()
    fId.SetLibItemName(pcbnew.UTF8("FOOTPRINT"))
    clone = pcbnew.Cast_to_FOOTPRINT(pcbnew.Cast_to_BOARD_ITEM(footprint.Clone()))
    clone.SetFPID(fId)

    pId = pattern.GetFPID()
    pId.SetLibItemName(pcbnew.UTF8("PATTERN"))

    pcbnew.FootprintSave(str(workingDir), clone)
    pcbnew.FootprintSave(str(workingDir), pattern)

    patternAst = loadAstWithoutTStamp(workingDir / "PATTERN.kicad_mod")
    footprintAst = loadAstWithoutTStamp(workingDir / "FOOTPRINT.kicad_mod")
    return areSameFootprints(footprintAst, patternAst)

def areSameFootprints(l: SExpr, r: SExpr) -> bool:
    simplifyAndCanonizeFpAst(l)
    simplifyAndCanonizeFpAst(r)
    return l == r

def loadAstWithoutTStamp(fname):
    with open(fname) as f:
        content = f.read()
    content = re.sub(r'\(tedit\s+[a-fA-F0-9]*\)|\(tstamp\s+[a-fA-F-0-9\-]*\)|hide', "", content)
    return parseSexprS(content)

def simplifyAndCanonizeFpAst(node: SExpr) -> SExpr:
    """
    Sorts nodes in the AST to make it somewhat canonic. This breaks, however,
    semantics of lists. Also, the complexity is quadratic.

    However, both properties are fine for footprint comparison
    """
    if isinstance(node, Atom):
        node.leadingWhitespace = ""
        return node
    node.leadingWhitespace = ""
    node.trailingWhitespace = ""

    def allowed(node):
        if isinstance(node, Atom):
            return node.value not in ["FOOTPRINT", "PATTERN"]
        if node.items[0].value == "property":
            return False
        if node.items[0].value == "fp_text":
            if len(node.items) >= 2 and isinstance(node.items[1], Atom):
                if node.items[1].value in ["value", "reference"]:
                    return False
        return True
    node.items = [simplifyAndCanonizeFpAst(x) for x in node.items if allowed(x)]
    node.items.sort(key=lambda x: str(x))
    return
