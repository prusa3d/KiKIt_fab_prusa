from __future__ import annotations

import enum
import glob
import os
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable, List, Optional, Tuple, TypeVar, Union

from kikit.eeschema_v6 import (Symbol, extractComponents,  # type: ignore
                               getField, getReference)

import prusaman

from ..bom import BomFilter, PnBFilter
from ..netlist import exportIBomNetlist
from ..params import RESOURCES
from ..project import PrusamanProject
from ..util import defaultTo, locatePythonInterpreter, zipFiles
from .panelStage import PanelStageMixin
from .validationStage import ValidationStageMixin
from .millStage import MillStageMixin
from .smtStage import SmtStageMixin
from .sourcingStage import SourcingStageMixin
from .common import BoardError

T = TypeVar("T")
OutputReporter = Callable[[str, str], None]  # Takes TAG and message
ContinuationPrompt = Callable[[str, str], bool] # Takes TAG, message and returns true if continue

def stderrReporter(tag: str, message: str) -> None:
    sys.stderr.write(f"{tag}: {message}\n")

def stdioPrompt(tag: str, message: str) -> None:
    r = input(f"{tag}: {message} [y/N]:")
    return r.lower() == "y"


class Severity(enum.Enum):
    Info = 0
    Warning = 1
    Error = 1

    def __str__(self) -> str:
        return [
            "INFO",
            "WARN",
            "ERROR"
        ][self.value]


class Manugenerator(ValidationStageMixin, PanelStageMixin, MillStageMixin,
                    SmtStageMixin, SourcingStageMixin):
    def __init__(self, project: PrusamanProject, outputdir: Union[str, Path],
                 reportInfo: Optional[OutputReporter]=None,
                 reportWarning: Optional[OutputReporter]=None,
                 reportError: Optional[OutputReporter]=None,
                 askContinuation: Optional[ContinuationPrompt]=None) -> None:
        """
        Construct the object that generates the output. This is an object
        instead of function, so we can implicitly pass reporters and other
        shared resources.

        - project: Prusaman project of the source
        - outputdir: Path to the output directory
        - configuration: you can optionally specify the configuration or the
                         configuration file. If it is not specified, it is
                         deduced from the project.
        - reportInfo: A callback to report logs
        - reportWarning: A callback to report warnings
        """
        self._project: PrusamanProject = project
        self._outputdir: Path = Path(outputdir)
        self._infoReporter: OutputReporter = defaultTo(reportInfo, stderrReporter)
        self._warningReporter: OutputReporter = defaultTo(reportWarning, stderrReporter)
        self._errorReporter: OutputReporter = defaultTo(reportError, stderrReporter)
        self._askContinuation: ContinuationPrompt = defaultTo(askContinuation, stdioPrompt)
        self._log: List[Tuple[Severity, str, str]] = []

    def _reportInfo(self, tag: str, message: str) -> None:
        self._log.append((Severity.Info, tag, message))
        self._infoReporter(tag, message)

    def _reportWarning(self, tag: str, message: str) -> None:
        self._log.append((Severity.Warning, tag, message))
        self._warningReporter(tag, message)

    def _reportError(self, tag: str, message: str) -> None:
        self._log.append((Severity.Error, tag, message))
        self._errorReporter(tag, message)

    def _askWarning(self, tag: str, prompt: str, error: str) -> None:
        if not self._askContinuation(tag, prompt):
            raise BoardError(error)

    def _userFail(self, message):
        """
        Logs the message and reports user input error
        """
        self._reportError(message)
        raise BoardError(message)

    def make(self) -> None:
        try:
            self._makeValidation()
            self._makePanelStage()
            self._makeMillStage()
            self._makeSmtStage()
            self._makeSourcingStage()
            self._copySrc()
        except Exception:
            raise
        finally:
            self._makeMetadata()
            finalArchive = self._outputdir / (self._project.getName() + ".zip")
            zipFiles(finalArchive, self._outputdir, None,
                [x for x in glob.glob(str(self._outputdir / "**" / "*")) if os.path.isfile(x)])

    def _makeMetadata(self):
        self._reportInfo("LOG", "Final log start")
        logfile = self._outputdir / "prusaman-info.txt"
        logfile.parent.mkdir(exist_ok=True, parents=True)
        self._reportInfo("LOG", "Final log directory created")
        with open(logfile, "w") as f:
            self._reportInfo("LOG", "Final opened")
            now = datetime.now()
            f.write(f"Prusaman version {prusaman.__version__}\n")
            f.write(f"Generated on {now.strftime('%d. %m. %Y, %H:%M:%S')}\n")
            f.write(f"\nThe build log follows:\n")
            self._writeLog(f)
        self._reportInfo("LOG", "Final log finished")

    def _writeLog(self, file):
        severityPad = max(map(lambda x: len(str(x[0])), self._log))
        tagPad = max(map(lambda x: len(x[1]), self._log))
        for severity, tag, message in self._log:
            if len(message) == 0:
                continue
            BODY = 80
            wMessages = message.split("\n")
            header = f"{severity:<{severityPad}}| {tag:>{tagPad}}: "
            head, *tail = wMessages
            file.write(f"{header}{head}\n")
            if len(tail) > 0:
                file.write(textwrap.indent("\n".join(tail), len(header) * " ") + "\n")

    def _copySrc(self) -> None:
        target = self._outputdir / self._fileName("SOURCE")
        target.mkdir(parents=True, exist_ok=True)

        source = self._project.getDir()

        # We build the list first and then copy. Otherwise, we can create an
        # infinite loop as we copy new and new files.
        fileList: Tuple[Path, Path] = [] # Source -> Target
        for root, _, files in os.walk(source):
            for f in files:
                path = Path(root) / f
                # Since already generated data can be in the source directory,
                # ignore them.
                if any(x.name.startswith("Prusaman_Export") for x in path.parents):
                    continue
                t = target / path.relative_to(source)
                fileList.append((path, t))
        for s, t in fileList:
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, t)

    def _fileName(self, prefix: str) -> str:
        return f"{prefix}-{self._project.getName()}"

    def _makeIbom(self, source: Path, outdir: Path) -> None:
        with NamedTemporaryFile(mode="w", prefix="ibomnet_", suffix=".net",
                                delete=False) as f:
            try:
                bom = extractComponents(str(self._project.getSchema()))
                exportIBomNetlist(f, bom)
                f.close()

                env = os.environ.copy()
                env["INTERACTIVE_HTML_BOM_NO_DISPLAY"] = "1"

                ibomBinary = RESOURCES / "ibom" / "InteractiveHtmlBom" / "generate_interactive_bom.py"
                command = [locatePythonInterpreter(), str(ibomBinary), "--no-browser",
                        "--dark-mode", "--extra-fields", "ID,Osazovat/Nakupovat",
                        "--name-format", "%f-ibom",
                        "--netlist-file", f.name,
                        "--dest-dir", str(outdir), str(source)]
                result = subprocess.run(command, capture_output=True, env=env)
                stdout = result.stdout.decode("utf-8")
                stderr = result.stderr.decode("utf-8")
                if result.returncode != 0:
                    self._reportError("IBOM", stdout)
                    self._reportError("IBOM", stderr)
                    message = f"Ibom generation of {source} failed with code {result.returncode}."
                    raise RuntimeError(message)
                self._reportInfo("IBOM", stdout)
                self._reportInfo("IBOM", stderr)
            finally:
                f.close()
                os.unlink(f.name)

    def _commonBomFilter(self, item: Symbol) -> bool:
        ref = getReference(item)
        if any(ref.startswith(pref) for pref in ["#", "M", "NT", "G"]):
            return False
        return True

    def _legacyBomAssemblyFilter(self, item: Symbol) -> bool:
        """
        Realize legacy BOM filter for assembly - i.e., start marks "do not fit"
        """
        id = defaultTo(getField(item, "id"), "")
        if id == "":
            raise BoardError(f"Symbol {getReference(item)} has empty ID - cannot proceed")
        return self._commonBomFilter(item) and id != "" and ("*" not in id)

    def _legacyBomSourcingFilter(self, item: Symbol) -> bool:
        """
        Realize legacy BOM filter for sourcing - i.e., source everything except
        parts marked with "*"
        """
        id = defaultTo(getField(item, "id"), "")
        if id == "":
            raise BoardError(f"Symbol {getReference(item)} has empty ID - cannot proceed")
        return self._commonBomFilter(item) and id != "*"

    def _iBomFilter(self, item: Symbol) -> bool:
        config = defaultTo(getField(item, "Config"), "")
        configs = [x.strip() for x in config.split(" ") if x.strip() != ""]

        allow = len(configs) == 0 or f"+{self._requestedConfig}" in configs
        return allow and self._commonBomFilter(item)

    @property
    def _bomFilter(self) -> BomFilter:
        return PnBFilter()
