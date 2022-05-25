from __future__ import annotations

from dataclasses import dataclass
import json
from kikit.units import readLength
import pcbnew

from typing import Callable, Dict, Any, Tuple

from prusaman.params import RESOURCES

@dataclass
class DesignRules:
    allowBlindVias: bool
    allowMicroVias: bool
    minimalClearance: int
    minimalTrackWidth: int
    minimalAnnularWidth: int
    minimalViaDiameter: int
    copperToHoleClearance: int
    copperToEdgeClearance: int
    minimalThroughHole: int
    holeToHoleClearance: int
    minimalMicroViaDiameter: int
    minimalMicroViaHole: int
    minimalSilkscreenClearance: int

    @staticmethod
    def _bdsPairs() -> Dict[str, str]:
        return {
            "allowBlindVias": "m_BlindBuriedViaAllowed",
            "allowMicroVias": "m_MicroViasAllowed",
            "minimalClearance": "m_MinClearance",
            "minimalTrackWidth": "m_TrackMinWidth",
            "minimalAnnularWidth": "m_ViasMinAnnularWidth",
            "minimalViaDiameter": "m_ViasMinSize",
            "copperToHoleClearance": "m_HoleClearance",
            "copperToEdgeClearance": "m_CopperEdgeClearance",
            "minimalThroughHole": "m_MinThroughDrill",
            "holeToHoleClearance": "m_HoleToHoleMin",
            "minimalMicroViaDiameter": "m_MicroViasMinSize",
            "minimalMicroViaHole": "m_MicroViasMinDrill",
            "minimalSilkscreenClearance": "m_SilkClearance",
        }

    @staticmethod
    def _readValue(v: Any) -> Any:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return int(readLength(v))

    @staticmethod
    def writeValue(v: Any) -> Any:
        if isinstance(v, bool):
            return v
        if isinstance(v, int):
            return f"{pcbnew.ToMM(v)}mm"

    @staticmethod
    def fromDict(d: Dict[str, Any]) -> DesignRules:
        try:
            transformedD = {
                k: DesignRules._readValue(v) for k, v in d.items()
            }
            return DesignRules(**transformedD)
        except Exception as e:
            if "unexpected keyword argument" in str(e):
                e = str(e)
                idx = e.rfind("'", 0, -2)
                e = f"Unknown parameter {e[idx+1:-1]}"
            raise RuntimeError(f"Invalid design rules specification: {e}") from None

    @staticmethod
    def fromName(name: str) -> DesignRules:
        paramsFile = RESOURCES / "designRules" / (name + ".json")
        if not paramsFile.exists():
            raise RuntimeError(f"Unknown technology params '{name}'")
        with open(paramsFile) as f:
            return DesignRules.fromDict(json.load(f))

    def settingsViolations(self, s: pcbnew.BOARD_DESIGN_SETTINGS) -> Dict[str, Tuple[Any, Any]]:
        """
        Given a board design settings, return a list of settings that differ
        """
        pairs = { name: (getattr(self, name), getattr(s, bdsName))
            for name, bdsName in self._bdsPairs().items() }
        diff = {}
        for k, (left, right) in pairs.items():
            if left != right:
                diff[k] = (left, right)
        return diff

    def applyTo(self, s: pcbnew.BOARD_DESIGN_SETTINGS) -> None:
        for name, bdsName in self._bdsPairs().items():
            setattr(s, bdsName, getattr(self, name))

