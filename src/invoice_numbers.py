import re


def normalized_invoice_numbers(values):
    """Return distinct invoice identifiers in their supplied order."""
    result = []
    for value in values or []:
        cleaned = re.sub(r"\s+", "", str(value or "")).strip("/")
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def combined_invoice_number(values):
    """Store multiple invoices in the existing DTR-compatible text column."""
    return " / ".join(normalized_invoice_numbers(values))

