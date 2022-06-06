from typing import Set, Tuple
import pcbnew # type: ignore

from kikit.eeschema_v6 import (Symbol, extractComponents,  # type: ignore
                               getField, getReference)

from ..util import splitOn

class BoardError(Exception):
    """
    This exception should mark all error that are related to invalid input. Such
    error isn't considered as a bug, but a problem with the user input.
    """
    pass

def collectStandardLayers(board: pcbnew.BOARD) -> Set[int]:
    layers = set([
        pcbnew.F_Mask,
        pcbnew.B_Mask,
        pcbnew.F_SilkS,
        pcbnew.B_SilkS,
        pcbnew.F_Paste,
        pcbnew.B_Paste,
        pcbnew.Edge_Cuts
    ])
    for layer in pcbnew.LSET_AllCuMask(board.GetCopperLayerCount()).CuStack():
        layers.add(layer)
    return layers

def naturalComponetKey(component: Symbol) -> Tuple[str, int]:
    text, num = splitOn(getReference(component), lambda x: not x.isdigit())
    return str(text), int(num)

def layerToSide(layer: int) -> str:
    if layer == pcbnew.F_Cu:
        return "top"
    if layer == pcbnew.B_Cu:
        return "bottom"
    raise RuntimeError(f"Got component with invalid layer {layer}")
