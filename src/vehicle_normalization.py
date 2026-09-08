import re


def canonical_vehicle_number(value):
    """Store and compare vehicle numbers in compact uppercase form."""
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
