from pcbnew import FromMM # type: ignore
from dataclasses import dataclass
from pathlib import Path

PKG_BASE = Path(__file__).resolve().parent
RESOURCES = Path(PKG_BASE) / "resources"

FOOTPRINT_REPO = "prusa3d/PrusaKicadLib"

# This is only a temporary override for initial testing
FOOTPRINT_REPO = "yaqwsx/PrusaKicadLib"

@dataclass
class GluStampType:
    dia: int
    stepsForward: int
    stepsBackwards: int
    type: int
    spacing: int

GLUE_STAMPS = { s.dia: s for s in [
    GluStampType(FromMM(0.97), 200, 50, 2, FromMM(0.203)),
    GluStampType(FromMM(1.26), 400, 50, 2, FromMM(0.203)),
    GluStampType(FromMM(1.59), 800, 50, 2, FromMM(0.35)),
    GluStampType(FromMM(1.83), 1200, 50, 2, FromMM(0.5)),
]}

MILL_RELEVANT_FOOTPRINTS = [
    "prusa_other:hole4cutter-1,5mm",
    "prusa_other:hole4cutter-2mm"
]
