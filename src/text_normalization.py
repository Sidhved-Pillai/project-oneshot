import re
from difflib import SequenceMatcher


COMMON_PLACES = (
    "Alandi", "Andheri", "Baroda", "Bhiwandi", "Indore", "Jhagadia", "Kamshet",
    "Kolhapur", "Kudus", "Mundhwa", "Pune", "Solapur", "Talegaon", "Thane",
    "Vadodara", "Vasai", "Wada", "Wagholi",
)


def _comparison(value):
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def _closest(value, candidates, threshold=0.84):
    source = _comparison(value)
    if not source:
        return ""
    usable = [str(candidate).strip() for candidate in candidates if str(candidate or "").strip()]
    exact = next((candidate for candidate in usable if _comparison(candidate) == source), None)
    if exact:
        return exact
    scored = [(SequenceMatcher(None, source, _comparison(candidate)).ratio(), candidate) for candidate in usable]
    score, candidate = max(scored, default=(0, ""))
    return candidate if score >= threshold else ""


def canonical_company(value, known=()):
    original = re.sub(r"\s+", " ", str(value or "")).strip()
    comparison = _comparison(original)
    if not comparison:
        return ""
    if SequenceMatcher(None, " ".join(comparison.split()[:2]), "saint gobain").ratio() >= 0.78:
        suffix = " - Gyproc" if "gyproc" in comparison else ""
        return f"Saint-Gobain India Private Limited{suffix}"
    return _closest(original, known, 0.88) or original


def canonical_location(value, known=()):
    original = re.sub(r"\s+", " ", str(value or "")).strip()
    if not original:
        return ""
    match = _closest(original, COMMON_PLACES, 0.82) or _closest(original, known, 0.88)
    if match:
        return match
    # Preserve detailed addresses, while making simple place names readable.
    return original.title() if re.fullmatch(r"[A-Za-z ]+", original) else original


def canonical_vehicle_capacity(value):
    original = re.sub(r"\s+", " ", str(value or "")).strip()
    match = re.search(r"\b0*(\d{1,3})\s*(?:M\s*T|TONS?)\b", original, re.I)
    return f"{int(match.group(1))} MT" if match else original.upper()


def plain_remark(*parts):
    text = " ".join(str(part or "") for part in parts)
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 ]", " ", text)).strip()
