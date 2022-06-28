import datetime
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List, Tuple
import keyring
from .common import BoardError
from ..drc import DesignRules
from ..schema import Schema
from ..footprintlib import PrusaFootprints, extractRevision, matchesFootprintPattern

import pcbnew # type: ignore

from kikit.drc import Violation, readBoardDrcExclusions, runBoardDrc


class ValidationStageMixin:
    def _makeValidation(self) -> None:
        self._reportInfo("VALIDATE", "Validation of the board started")
        sch = self._project.schema
        board = self._project.board

        self._validateProjectVars()
        self._validateTitleBlock(sch, board)
        self._validateDesignRules()
        self._validateFootprints()
        self._ensurePassingDrc(board, "source board")
        self._reportInfo("VALIDATE", "Validation of the board finished")

    def _validateTitleBlock(self, schema: Schema, board: pcbnew.BOARD) -> None:
        schBlock = schema.titleBlock
        pcbBlock = board.GetTitleBlock()

        schRev = schBlock.get("rev", "").strip()
        if schRev == "":
            self._userFail("Missing revision in schematics. Cannot continue.")
        pcbRev = pcbBlock.GetRevision().strip()
        if pcbRev == "":
            raise BoardError("Missing revision in board. Cannot continue.")
        if pcbRev != schRev:
            self._askWarning("TITLE",
                f"The revisions do not match (PCB: {pcbRev} vs SCH: {schRev}). Ignore error and continue?",
                f"The revisions do not match (PCB: {pcbRev} vs SCH: {schRev}).")

    def _validateProjectVars(self) -> None:
        if "ID" not in self._project.textVars:
            self._userFail("The project has not ID specified")
        if "TECHNOLOGY_PARAMS" not in self._project.textVars:
            self._askWarning("TECHNOLOGY",
                "Missing TECHNOLOGY_PARAMS in project variables. Ignore and continue?",
                "Missing TECHNOLOGY_PARAMS in project variables.")
            self._reportWarning("TECHNOLOGY", "TECHNOLOGY_PARAMS is not set, no rules are enforced.")

    def _validateDesignRules(self) -> None:
        # This is temporary before we migrate all projects
        if "TECHNOLOGY_PARAMS" not in self._project.textVars:
            return
        paramsName = self._project.textVars["TECHNOLOGY_PARAMS"]
        designRules = DesignRules.fromName(paramsName)
        board = self._project.board
        violations = designRules.settingsViolations(board.GetDesignSettings())
        if len(violations) == 0:
            return
        for name, (left, right) in violations.items():
            self._reportError("DRC", f"Wrong board setting {name}. " + \
                f"{DesignRules.writeValue(left)} expected, got {DesignRules.writeValue(right)}")
        raise BoardError("Invalid board design rules.")

    def _validateFootprints(self) -> None:
        self._reportInfo("FOOTPRINTS", "Footprint validation started")

        token = self._obtainGhToken()
        if token is None:
            return

        fLib = PrusaFootprints(token)
        if fLib.getLocalRevision() != fLib.getRemoteRevision():
            self._reportInfo("FOOTPRINTS", "Pulling new library version from GitHub")
            fLib.updateFromRemote()

        warnings = False
        def reportWarning(*args, **kwargs):
            nonlocal warnings
            warnings = True
            self._reportWarning(*args, **kwargs)

        revisionCache: Dict[Tuple[str, str], str] = {}

        with TemporaryDirectory(suffix=".pretty") as tmpLib:
            for footprint in self._project.board.Footprints():
                reference = footprint.Reference().GetText()
                id = footprint.GetFPID()
                libName = str(id.GetLibNickname())
                fName = str(id.GetLibItemName())
                if libName == "prusa_waiting_for_approval":
                    reportWarning("FOOTPRINT",
                        f"{footprint.Reference()} comes from prusa_waiting_for_approval.")
                if libName not in ["prusa_con", "prusa_other"]:
                    continue
                if (libName, fName) in revisionCache:
                    patternRev = revisionCache[(libName, fName)]
                else:
                    pattern = fLib.getFootprint(libName, fName)
                    if pattern is None:
                        reportWarning("FOOTPRINT",
                            f"{libName}:{fName} ({reference}) doesn't exist in Github library")
                        continue
                    patternRev = extractRevision(pattern)
                    revisionCache[(libName, fName)] = patternRev
                footprintRev = extractRevision(footprint)
                if patternRev is None:
                    reportWarning("FOOTPRINT", f"{libName}:{fName} is missing revision on GitHub. " +
                        "There is something wrong in the library. Please, report it." )
                if patternRev == footprintRev:
                    # The revision is the most up-to-date, no more checks to perform
                    continue
                revsplit = patternRev.split("-", 1)
                gitrev = revsplit[0]
                date = datetime.datetime.fromisoformat(revsplit[1])
                datestr = date.strftime("%d. %m. %Y, %H:%M")
                reportWarning("FOOTPRINT", f"Footprint of {reference} is out of date, " +
                                           f"there is a newer version of {libName}:{fName}: {gitrev} ({datestr})")
            if warnings:
                self._askWarning("FOOTPRINT",
                    "There are footprint validation errors, ignore and continue?",
                    "Footprint validation failed")

        self._reportInfo("FOOTPRINTS", "Footprint validation finished")

    def _getTokenFromKeyring(self):
        try:
            return keyring.get_password("prusaman", "github")
        except Exception as e:
            return None

    def _obtainGhToken(self):
        tokenObtainMethods = [
            lambda: os.environ.get("PRUSAMAN_GH_TOKEN", ""),
            self._getTokenFromKeyring
        ]

        token = None
        for method in tokenObtainMethods:
            token = method()
            if token is not None and len(token.strip()) > 0:
                break
            token = None
        if token is None:
            self._askWarning("FOOTPRINTS",
                "The GitHub access token is not setup, cannot fetch footprints. Skip footprint check and continue?",
                "Cannot pull footprint library from GitHub due to unconfigured access token. See installation instructions.")
        return token

    def _ensurePassingDrc(self, board: pcbnew.BOARD, name) -> None:
        self._reportInfo("DRC", f"Running DRC for {name}")
        report = runBoardDrc(board, True)
        report.pruneExclusions(readBoardDrcExclusions(board))

        def reportResult(res: List[Violation], type: str) -> bool:
            errorCount = 0
            ERROR_LIMIT = 50

            if len(res) == 0:
                return False
            report = self._reportError if type == "error" else self._reportWarning
            report("DRC", f"There are {len(res)} DRC {type}s:")
            for v in res:
                errorCount += 1
                if errorCount > ERROR_LIMIT:
                    continue
                report("DRC", f"{name}: {v.format(pcbnew.EDA_UNITS_MILLIMETRES)}")
            if errorCount > ERROR_LIMIT:
                report("DRC", f"First {ERROR_LIMIT} errors, shown, omitting rest of the {errorCount} errors for brevity")
            return True

        getWarnings = lambda l: [x for x in l if x.severity == "warning"]
        getErrors = lambda l: [x for x in l if x.severity == "error"]

        reportResult(getWarnings(report.drc), "warning")
        drcErrors = reportResult(getErrors(report.drc), "error")

        reportResult(getWarnings(report.unconnected), "warning")
        unconnectedErrors = reportResult(getErrors(report.drc), "error")

        reportResult(getWarnings(report.footprint), "warning")
        footprintErrors = reportResult(getErrors(report.footprint), "error")

        if drcErrors or unconnectedErrors or footprintErrors:
            self._askWarning("DRC",
                            f"There are DRC errors in {name}. See the log. Ignore them and continue?",
                            f"There are DRC errors in {name}. See the log.")
        self._reportInfo("DRC", f"Running DRC for {name} finished")
