#!/usr/bin/env python3

import ast
import sys
import astunparse
from typing import Any

class RemovePrints(ast.NodeTransformer):
    def visit_Call(self, node: ast.Call) -> Any:
        f = node.func
        if isinstance(f, ast.Name) and f.id == "print":
            return ast.Pass()
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        if node.name == "_get_git_version":
            node.body = [ast.Return(ast.Name("LAST_TAG", ast.Load))]
        return node

if __name__ == "__main__":
    t = ast.parse(open(sys.argv[1]).read())
    RemovePrints().visit(t)
    print(astunparse.unparse(t))
