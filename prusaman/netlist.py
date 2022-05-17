from typing import List, TextIO
from kikit.eeschema_v6 import Symbol


def exportIBomNetlist(file: TextIO, symbols: List[Symbol]) -> None:
    """
    Given a list of symbols, generate a simplified netlist suitable for iBom.
    Only the necessary fields are populated
    """
    file.write("""
    (export (version "E")
        (design
            (source "")
            (date "")
            (tool "Prusaman")
            (sheet)
        )
        (libparts)
        (libraries)
        (nets)
        (components
    """)
    for s in symbols:
        exportSymbol(file, s)

    file.write("))")

def exportSymbol(file: TextIO, symbol: Symbol) -> None:
    file.write("(comp ")
    file.write(f'(ref "{symbol.properties["Reference"]}") ')
    file.write(f'(value "{symbol.properties["Value"]}") ')
    file.write(f'(footprint "{symbol.properties["Footprint"]}") ')

    file.write("(fields ")
    for key, value in symbol.properties.items():
        if key in ["Reference", "Value", "Footprint"]:
            continue
        file.write(f'(field (name "{key}") "{value}") ')
    file.write(" ) ") # Fields

    file.write(" )\n")

