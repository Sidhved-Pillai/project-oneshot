"""Vijay/Andheri route normalization backed by the supplied trip master."""

import json
import re
from functools import lru_cache
from pathlib import Path


_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "vijay_delivery_addresses.json"
_NOISE = {
    "address", "and", "at", "dist", "district", "india", "maharashtra", "near",
    "no", "road", "shop", "state", "tal", "the",
}


def _tokens(value):
    return {
        token for token in re.findall(r"[a-z0-9]+", str(value or "").casefold())
        if len(token) > 1 and token not in _NOISE
    }


def _display_short(value):
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return value.title()


@lru_cache(maxsize=1)
def _master_rows():
    with _DATA_FILE.open(encoding="utf-8") as source:
        return json.load(source)


def canonical_vijay_location(value, *, origin=False):
    """Return the master-file short address when a full address is recognizable.

    Conservative token coverage prevents a bare city such as ``Palghar`` from
    being matched to an arbitrary customer that happens to share that city.
    """
    original = re.sub(r"\s+", " ", str(value or "")).strip()
    if not original:
        return ""
    tokens = _tokens(original)

    # Vijay loads from Bisleri's Palghar print compound; keep only its locality.
    if origin and "palghar" in tokens and ({"vivan", "neelam", "compound"} & tokens):
        return "Palghar"

    best = (0.0, "")
    for row in _master_rows():
        address_tokens = _tokens(row["full_address"])
        identity_tokens = address_tokens | _tokens(row["name"])
        for code in row.get("customer_codes", []):
            identity_tokens |= _tokens(code)
        overlap = len(tokens & identity_tokens)
        if overlap < 3:
            continue
        coverage = overlap / max(1, min(len(tokens), len(identity_tokens)))
        address_coverage = len(tokens & address_tokens) / max(1, min(len(tokens), len(address_tokens)))
        score = max(coverage, address_coverage)
        if score > best[0]:
            best = (score, row["short_address"])
    return _display_short(best[1]) if best[0] >= 0.62 else original

