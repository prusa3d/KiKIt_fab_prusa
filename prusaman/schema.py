from __future__ import annotations
from typing import Dict, Iterable, Union
from kikit.sexpr import SExpr, Atom, parseSexprF
from dataclasses import dataclass
from pathlib import Path

AstNode = Union[SExpr, Atom]

def isElement(name: str) -> callable[[AstNode], bool]:
    def f(node: AstNode) -> bool:
        if isinstance(node, Atom) or len(node) == 0:
            return False
        item = node[0]
        return isinstance(item, Atom) and item.value == name
    return f

def readDict(items: Iterable[SExpr]) -> Dict[str, str]:
    vals = {}
    for item in items:
        assert len(item.items) == 2
        key = item.items[0]
        value = item.items[1]
        assert isinstance(key, Atom) and isinstance(value, Atom)
        vals[key.value] = value.value
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
                titleBlock = readDict(item.items[1:])
        return Schema(
            paper=paper,
            titleBlock=titleBlock)

