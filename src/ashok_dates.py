"""Month-aware entry dates, separately loaded during Streamlit hot deployments."""
import datetime as dt

from .dtr_dates import parse_dtr_date


def parse_month_date(value, reference):
    """Resolve DD/MM or MM/DD against a known month without inventing a date."""
    parsed = parse_dtr_date(value)
    if parsed is None or reference is None:
        return None
    if (parsed.year, parsed.month) == (reference.year, reference.month):
        return parsed
    try:
        swapped = dt.date(parsed.year, parsed.day, parsed.month)
    except ValueError:
        return None
    return swapped if (swapped.year, swapped.month) == (reference.year, reference.month) else None
