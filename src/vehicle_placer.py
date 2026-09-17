"""Canonical names for the person who placed a vehicle."""

import re
from difflib import SequenceMatcher


CANONICAL_VEHICLE_PLACERS = ("Nitish Jha", "Ajit Thakur", "Manish Jha", "Ashok")
LOGIN_VEHICLE_PLACERS = {
    "Nitish": "Nitish Jha", "Ajit": "Ajit Thakur", "Manish": "Manish Jha", "Ashok": "Ashok",
}
LEGACY_VEHICLE_PLACERS = {"ashokbhai": "Ashok", "ashok bhai": "Ashok"}


def canonical_vehicle_placer(value):
    original = str(value or "").strip()
    normalized = " ".join(re.findall(r"[a-z]+", original.casefold()))
    if not normalized:
        return original
    if normalized in LEGACY_VEHICLE_PLACERS:
        return LEGACY_VEHICLE_PLACERS[normalized]
    login_aliases = {login.casefold(): full_name for login, full_name in LOGIN_VEHICLE_PLACERS.items()}
    if normalized in login_aliases:
        return login_aliases[normalized]
    words = normalized.split()
    for canonical in CANONICAL_VEHICLE_PLACERS:
        target = canonical.casefold()
        if normalized == target:
            return canonical
        target_words = target.split()
        full_score = SequenceMatcher(None, normalized, target).ratio()
        word_match = len(words) == 2 and all(
            SequenceMatcher(None, word, target_word).ratio() >= 0.78
            for word, target_word in zip(words, target_words)
        )
        if full_score >= 0.82 or word_match:
            return canonical
    return original
