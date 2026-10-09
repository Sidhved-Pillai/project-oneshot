"""Unambiguous parsing of DTR dates, including ISO dates stored in JSON."""
import datetime as dt
import re
from numbers import Number

import pandas as pd


def parse_dtr_date(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (dt.datetime, dt.date, pd.Timestamp)):
        return pd.Timestamp(value).date()
    # Never interpret spreadsheet serials or year numbers as Unix nanoseconds.
    if isinstance(value, Number):
        return None
    value = str(value).strip()
    if not value or value.isdigit():
        return None
    iso = bool(re.match(r"^\d{4}-\d{2}-\d{2}(?:$|[ T])", value))
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=not iso)
    return None if pd.isna(parsed) else parsed.date()


def dtr_editor_key(rows, start, end):
    import hashlib
    import json
    version = [(row.get("request_number"), row.get("updated_at"), row.get("dtr_data")) for row in rows]
    digest = hashlib.sha256(json.dumps(version, default=str, sort_keys=True).encode()).hexdigest()[:20]
    return f"dtr_live_editor_v2_{start}_{end}_{digest}"
