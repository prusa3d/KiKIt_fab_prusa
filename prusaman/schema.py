from __future__ import annotations
from typing import Dict, Iterable, Union
from kikit.sexpr import SExpr, Atom, parseSexprF, isElement
from dataclasses import dataclass
from pathlib import Path

def readTitleBlock(items: Iterable[SExpr]) -> Dict[str, str]:
    vals = {}
    for item in items:
        assert all(isinstance(x, Atom) for x in item.items)
        if isElement("comment")(item):
            key = item.items[0].value
            seq = item.items[1].value
            value = item.items[2].value
            vals[f"{key}{seq}"] = value
        else:
            key = item.items[0].value
            value = item.items[1].value
            vals[key] = value
    return vals

@dataclass
class Schema:
    paper: str
    titleBlock: Dict[str, str]

    @staticmethod
    def fromFile(path: Union[str, Path]) -> Schema:
        with open(path, "r") as f:
            ast = parseSexprF(f)
        paper = ""
        titleBlock = {}
        for item in ast.items:
            if isElement("paper")(item):
                paper = item.items[1].value
            if isElement("title_block")(item):
                titleBlock = readTitleBlock(item.items[1:])
        return Schema(
            paper=paper,
            titleBlock=titleBlock)

