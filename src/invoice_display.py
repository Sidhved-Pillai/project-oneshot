"""Readable multi-invoice DTR cells without splitting structured invoice IDs."""
import re


def dtr_invoice_text(value):
    if value is None:
        return ''
    values = value if isinstance(value, (list, tuple)) else [value]
    invoices = []
    for item in values:
        # Legacy multi-invoice cells used spaced slashes. Unspaced slashes,
        # including GST/GST/0885/26-27, belong to the identifier itself.
        for part in re.split(r'\s+/\s+|[,;\n]+', str(item)):
            part = part.strip()
            if part and part.casefold() not in ('nan', 'none') and part not in invoices:
                invoices.append(part)
    return ', '.join(invoices)
