from typing import Any, Dict, Optional, Union
from kikit.eeschema_v6 import Symbol, getField, getReference # type: ignore

from prusaman.util import defaultTo

class BomFilter:
    """
    This class implements a BOM filter - basically two functions that decide if
    an item should or shouldn't be included in the BOM for sourcing and SMT
    assembly.
    """
    SPECIAL_REFERENCES = ["#", "M", "NT", "G"]

    def assemblyFilter(self, symbol: Symbol) -> bool:
        raise NotImplementedError("BomFilter is a base class")

    def sourcingFilter(self, symbol: Symbol) -> bool:
        raise NotImplementedError("BomFilter is a base class")

    def _commonFilter(self, symbol: Symbol) -> bool:
        ref = getReference(symbol)
        return symbol.unit == 1 and not any(ref.startswith(pref) for pref in self.SPECIAL_REFERENCES)

class LegacyFilter(BomFilter):
    """
    This filter realizes the legacy BOM style (with stars)
    """
    def assemblyFilter(self, symbol: Symbol) -> bool:
        id = defaultTo(getField(symbol, "id"), "")
        if id == "":
            raise RuntimeError(f"Symbol {getReference(symbol)} has empty ID - cannot proceed")
        return self._commonFilter(symbol) and id != "" and ("*" not in id)

    def sourcingFilter(self, symbol: Symbol) -> bool:
        id = defaultTo(getField(symbol, "id"), "")
        if id == "":
            raise RuntimeError(f"Symbol {getReference(symbol)} has empty ID - cannot proceed")
        return self._commonFilter(symbol) and id != "*"

class PnBFilter(BomFilter):
    """
    This implements the Populate-Buy filter
    """
    def assemblyFilter(self, symbol: Symbol) -> bool:
        pnb = self._getPnbField(symbol)
        return getReference(symbol).startswith("FID") or \
               (self._commonFilter(symbol) and pnb == "")


    def sourcingFilter(self, symbol: Symbol) -> bool:
        pnb = self._getPnbField(symbol)
        return self._commonFilter(symbol) and pnb in ["", "#"]

    def _getPnbField(self, symbol: Symbol) -> str:
        allowedValues = ["#", "dnf", ""]
        for n in ["PnB", "PNB", "pnb"]:
            pnb = getField(symbol, n)
            if pnb is not None:
                assert isinstance(pnb, str)
                pnbLower = pnb.lower().strip()
                if pnbLower not in allowedValues:
                    raise RuntimeError(
                        f"Component {getReference(symbol)} " + \
                        f"has invalid PnB field value '{pnb}'. " + \
                        f"Allowed values are: {', '.join(allowedValues)}")
                return pnbLower
        return ""

