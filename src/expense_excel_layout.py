"""Compact expense-ledger layout; one heading per row without duplicating payments."""
from decimal import Decimal
import json
import re

from .pnl_report import REPORT_EXPENSE_COLUMNS
from .record_integrity import expense_summary

DIRECT_EXPENSE_EXPORT_COLUMNS = [
    'Date', 'Amount', 'Expense Heading', 'Created By', 'Branch',
    'Vehicle Number', 'Vehicle Capacity', 'Own / Outside', 'Beneficiary Name',
    'Account Number', 'IFSC Code', 'Diesel', 'Diesel Qty', 'Diesel Rate',
    'Total Advance', 'Payment Mode', 'Remarks',
]


def canonical_heading(value):
    name = ' '.join(str(value or '').split())
    key = re.sub(r'[^a-z]', '', name.casefold())
    if key in {'routeexpense', 'routeexpenses', 'routeexpenseupi', 'routeexpensesupi'}:
        return 'Route expense'
    return next((known for known in REPORT_EXPENSE_COLUMNS if known.casefold() == name.casefold()), name)


def expense_excel_rows(records, exported):
    output = []
    for record, item in zip(records, exported):
        # Validate using the same authoritative category amounts as Records/P&L.
        summary = expense_summary(record)
        raw = record.get('dtr_data') or {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError):
                raw = {}
        categories = raw.get('categories', {}) if isinstance(raw, dict) else {}
        categories = categories if isinstance(categories, dict) else {}
        lines = {}
        for heading, value in categories.items():
            amount = Decimal(str(value or 0))
            if amount > 0:
                name = canonical_heading(heading)
                lines[name] = lines.get(name, Decimal(0)) + amount
        if not lines:
            # A legacy record without category amounts cannot safely be split.
            lines[canonical_heading(summary.get('expense_type') or record.get('expense_type'))] = (
                Decimal(str(summary.get('amount', record.get('amount')) or 0)))
        for index, (heading, amount) in enumerate(lines.items()):
            row = {**item, 'Expense Heading': heading, 'Amount': float(amount)}
            if record.get('_trip_route_expense'):
                # This export includes only the trip's route cost, not its freight
                # advances or diesel, which are unrelated to this expense line.
                upi = Decimal(str(record.get('upi') if record.get('upi') is not None else raw.get('UPI', 0)))
                paid = min(amount, max(Decimal(0), upi))
                row.update({'Diesel': None, 'Diesel Qty': None, 'Diesel Rate': None,
                            'Total Advance': float(paid), 'Payment Mode': 'UPI' if paid else ''})
            elif index:
                # Payments belong to the saved record as a whole. Repeating
                # them on each category line would inflate Excel column totals.
                row.update({name: None for name in
                            ('Diesel', 'Diesel Qty', 'Diesel Rate', 'Total Advance', 'Payment Mode')})
            output.append({name: row.get(name, '') for name in DIRECT_EXPENSE_EXPORT_COLUMNS})
    return output
