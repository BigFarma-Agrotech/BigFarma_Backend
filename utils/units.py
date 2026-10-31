"""Units farmers sell in, and parsing of product quantity strings like "100 kg".

Units are stored in their singular form ("bag", "head"). Older products used
plural or alternative spellings ("bags", "liters"), which normalize_unit maps
onto the current names. Unknown units are kept as typed (lower-cased), so a
farmer is never blocked by a missing unit.
"""
import re
from typing import Optional, Tuple

# Sold in whole numbers only (you can't buy half a head of cattle)
COUNT_UNITS = {
    "piece", "head", "dozen", "tuber", "bunch", "bundle",
    "bag", "sack", "crate", "tray", "basket", "carton", "pack", "box",
    "mudu", "derica", "paint bucket", "congo",
}

UNIT_ALIASES = {
    "kgs": "kg", "kilogram": "kg", "kilograms": "kg",
    "grams": "g", "gram": "g",
    "tonnes": "tonne", "tons": "tonne", "ton": "tonne",
    "lbs": "lb", "pounds": "lb",
    "liters": "litre", "liter": "litre", "litres": "litre", "l": "litre",
    "gallons": "gallon", "jerrycans": "jerrycan",
    "pieces": "piece", "pcs": "piece", "pc": "piece",
    "heads": "head", "dozens": "dozen", "tubers": "tuber",
    "bunches": "bunch", "bundles": "bundle",
    "bags": "bag", "sacks": "sack", "crates": "crate", "trays": "tray",
    "baskets": "basket", "cartons": "carton", "packs": "pack", "boxes": "box",
    "mudus": "mudu", "dericas": "derica", "paint buckets": "paint bucket", "congos": "congo",
}

_QUANTITY = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(.*?)\s*$")


def normalize_unit(unit: Optional[str]) -> Optional[str]:
    if not unit or not unit.strip():
        return None
    key = " ".join(unit.strip().lower().split())
    return UNIT_ALIASES.get(key, key)


def parse_quantity(quantity: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """ "100 kg" -> (100.0, "kg"); "2.5 liters" -> (2.5, "litre"); "lots" -> (None, None)."""
    match = _QUANTITY.match(str(quantity or ""))
    if not match:
        return None, None
    return float(match.group(1)), normalize_unit(match.group(2))


def is_count_unit(unit: Optional[str]) -> bool:
    return normalize_unit(unit) in COUNT_UNITS


# Units that keep their form in the plural ("10 kg", "5 head")
_NO_PLURAL = {"kg", "g", "lb", "ml", "head", "dozen", "tonne"}
_PLURALS = {"box": "boxes", "bunch": "bunches", "paint bucket": "paint buckets"}


def unit_label(amount: float, unit: Optional[str]) -> str:
    """unit_label(1, "bag") -> "bag"; unit_label(3, "bag") -> "bags" """
    name = normalize_unit(unit) or ""
    if not name or float(amount) == 1 or name in _NO_PLURAL:
        return name
    return _PLURALS.get(name, f"{name}s")


def format_quantity(amount: float, unit: Optional[str]) -> str:
    """ (5.0, "kg") -> "5 kg"; (3, "bag") -> "3 bags" """
    number = f"{amount:g}"
    label = unit_label(amount, unit)
    return f"{number} {label}" if label else number
