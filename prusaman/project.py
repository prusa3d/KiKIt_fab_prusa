from typing import Optional, Union
from pathlib import Path

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
        return PrusamanProject._resolveProjectNameV5(path)

    @staticmethod
    def _resolveProjectNameV5(path: Path) -> str:
        candidate: Optional[str] = None
        for item in path.iterdir():
            if not item.name.endswith(".pro"):
                continue
            if candidate is not None:
                raise RuntimeError(f"There are multiple projects ({candidate} " +
                                   f"and {item.name}) in directory {path}. Not " +
                                   f"clear which one to choose.")
            candidate = item.name
        if candidate is not None:
            return candidate[:-len(".pro")]
        raise RuntimeError(f"No project found in {path}")

    @staticmethod
    def _oneOf(*args: Path) -> Path:
        for path in args:
            if path.exists():
                return path
        raise FileNotFoundError("None of : " + ", ".join([str(x) for x in args]) + " exists")

    def getConfiguration(self) -> Path:
        return self._projectdir / "prusaman.yaml"

    def getProject(self) -> Path:
        return self._oneOf(
            self._projectdir / f"{self._name}.kicad_pro",
            self._projectdir / f"{self._name}.pro"
        )

    def getBoard(self) -> Path:
        return self._projectdir / f"{self._name}.kicad_pcb"

    def getSchema(self) -> Path:
        return self._oneOf(
            self._projectdir / f"{self._name}.kicad_sch",
            self._projectdir / f"{self._name}.sch"
        )

    def getName(self) -> str:
        return self._name

    def getPanelReadmeTemplate(self) -> Path:
        return self._projectdir / "readme.panel.template.txt"

    def getMillReadmeTemplate(self) -> Path:
        return self._projectdir / "readme.freza.template.txt"

    def getDir(self) -> Path:
        return self._projectdir
