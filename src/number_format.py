"""Display helpers for Indian lakh/crore digit grouping."""

import math


def indian_number(value, decimals=2):
    """Format a number as 12,34,567.89 while keeping a fixed decimal count."""
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if not math.isfinite(amount):
        amount = 0.0
    rounded = f"{abs(amount):.{decimals}f}"
    whole, dot, fraction = rounded.partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while head:
            groups.append(head[-2:])
            head = head[:-2]
        whole = ",".join(reversed(groups)) + "," + tail
    sign = "-" if amount < 0 and float(rounded) else ""
    return f"{sign}{whole}{dot}{fraction}" if decimals else f"{sign}{whole}"


def format_inr(value, decimals=2):
    return f"₹{indian_number(value, decimals)}"
