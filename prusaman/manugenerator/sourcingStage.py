

import csv
from typing import List, TextIO

from kikit.eeschema_v6 import (Symbol, extractComponents,  # type: ignore
                               getField, getReference)

from .common import BoardError
from ..util import groupBy, zipFiles, splitOn
from ..bom import BomFilter



class SourcingStageMixin:
    def _makeSourcingStage(self) -> None:
        self._reportInfo("SOURCING", "Starting sourcing stage")
        sourcingName = self._fileName("NAKUP")
        outdir = self._outputdir / sourcingName
        outdir.mkdir(parents=True, exist_ok=True)

        sourcingListName = outdir / (self._project.getName() + "_BOM.csv")
        zipName = outdir / (self._project.getName() + "_BOM.zip")

        bomFilter = self._bomFilter

        bom = extractComponents(str(self._project.getSchema()))
        self._checkAnnotation(bom)
        bom = [x for x in bom if bomFilter.sourcingFilter(x)]

        grouppedBom = groupBy(bom, key=lambda c: (
            getField(c, "ID"),
            getField(c, "Footprint"),
            getField(c, "Value"),
        ))
        groups = list(grouppedBom.values())
        groups.sort(key=lambda g: (getReference(g[0])[:1], len(g)))

        with open(sourcingListName, "w", newline="") as f:
            self._makeSourcingBom(f, groups, bomFilter)

        zipFiles(zipName, outdir, None, [sourcingListName])
        self._reportInfo("SOURCING", "Sourcing stage finished")

    def _makeSourcingBom(self, bomFile: TextIO, groups: List[List[Symbol]],
                            bomFilter: BomFilter) -> None:
        writer = csv.writer(bomFile)
        writer.writerow(["Id", "Component", "Quantity per PCB", "Value"])

        for i, group in enumerate(groups):
            if len(group) == 0 or not bomFilter.assemblyFilter(group[0]):
                continue
            writer.writerow([
                getField(group[0], "ID"), i + 1, len(group),
                getField(group[0], "Value")])
        writer.writerow([])
        writer.writerow([])
        for i, group in enumerate(groups):
            if len(group) == 0 or bomFilter.assemblyFilter(group[0]):
                continue
            writer.writerow([
                getField(group[0], "ID"), i + 1, len(group),
                getField(group[0], "Value")])

    def _checkAnnotation(self, bom: List[Symbol]) -> None:
        unann = {}
        wrongAnn = []
        for s in bom:
            ref = getReference(s)
            if "?" in ref:
                unann[ref] = unann.get(ref, 0) + 1
                continue
            text, num = splitOn(ref, lambda x: not x.isdigit())
            if not num.isdigit():
                self._reportError("ANNOTATION", f"Component {ref} has invalid annotation.")
        for ref, c in unann.items():
            self._reportError("ANNOTATION", f"There {c}× unanotated components with {ref}")
        if len(unann) > 0 or len(wrongAnn):
            raise BoardError("The schematics contains annotation error.")
