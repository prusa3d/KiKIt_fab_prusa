import json
from typing import Any, Dict, Optional, Union
from pathlib import Path
from functools import cached_property
from prusaman.schema import Schema
import pcbnew

class PrusamanProject:
    """
    This code represents a KiCAD project and allows easy access to individual
    files without the need to hassle with project names.
    """
    def __init__(self, path: Union[str, Path]) -> None:
        self._projectdir: Path = Path(path).resolve()
        name = None
        if str(path).endswith(".kicad_pro"):
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

    def getMillReadmeTemplate(self) -> Path:
        return self._projectdir / "readme.freza.template.txt"

    def getDir(self) -> Path:
        return self._projectdir

    def has(self, file: Union[str, Path]):
        return (self._projectdir / file).exists()

    @cached_property
    def schema(self) -> Schema:
        return Schema.fromFile(self.getSchema())

    @property
    def board(self) -> pcbnew.BOARD:
        return pcbnew.LoadBoard(str(self.getBoard()))

    @cached_property
    def projectJson(self) -> Dict[str, Any]:
        with open(self.getProject(), "r") as f:
            return json.load(f)

    @cached_property
    def textVars(self) -> Dict[str, str]:
        return self.projectJson.get("text_variables", {})
