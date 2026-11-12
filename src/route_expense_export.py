"""Read-only route-expense projections for exports, never additional saved expenses."""
import datetime as dt
import json
from decimal import Decimal, InvalidOperation
from .vehicle_normalization import canonical_vehicle_number

ROUTE_EXPENSE = 'Route expense'


def data(value):
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or '{}')
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def amount(value):
    try:
        parsed = Decimal(str(value or 0).replace(',', ''))
        return float(parsed) if parsed.is_finite() and parsed > 0 else 0.0
    except (ValueError, TypeError, InvalidOperation):
        return 0.0


def trip_route_amount(row):
    if row.get('report_scope') == 'Expense' or row.get('is_archived') or row.get('status') == 'Cancelled':
        return 0.0
    raw = data(row.get('dtr_data'))
    for key in (ROUTE_EXPENSE, 'Route Expense', 'Route Expense (UPI)'):
        if key in raw:
            return amount(raw[key])
    # The own-vehicle workflow labels UPI as Route Expense. Outside-vehicle
    # UPI is a transporter advance, already included in transporter freight.
    if str(row.get('ownership_type') or raw.get('Own/Outside Veh.') or '').strip().casefold().startswith('own'):
        return amount(row['upi'] if row.get('upi') is not None else raw.get('UPI'))
    return 0.0


def route_export_row(row):
    value = trip_route_amount(row)
    if not value:
        return None
    return {**row, '_trip_route_expense':True, 'amount':value, 'expense_type':ROUTE_EXPENSE,
            'dtr_data':{**data(row.get('dtr_data')), 'categories':{ROUTE_EXPENSE:value}}}


def direct_expense_download_records(expenses, source_rows, filters, without_evidence=False):
    """Append eligible trip route costs using the same scope and applied filters."""
    output = list(expenses)
    seen = {r.get('request_number') for r in output if r.get('request_number')}
    if filters.get('heading', 'All') not in ('All', ROUTE_EXPENSE):
        return output
    for source in source_rows:
        row = route_export_row(source)
        if row is None or row.get('request_number') in seen:
            continue
        raw = data(row.get('dtr_data'))
        date = row.get('trip_date')
        if isinstance(date, dt.datetime):
            date = date.date()
        elif isinstance(date, str):
            try:
                date = dt.date.fromisoformat(date[:10])
            except ValueError:
                continue
        if not date or not filters['start'] <= date <= filters['end']:
            continue
        if filters.get('vehicle', 'All') != 'All' and canonical_vehicle_number(row.get('vehicle_number')) != filters['vehicle']:
            continue
        if filters.get('lr_number', '').strip().casefold() not in str(raw.get('LR No.') or '').casefold():
            continue
        if filters.get('invoice_number', '').strip().casefold() not in str(row.get('invoice_number') or raw.get('Invoice No.') or '').casefold():
            continue
        requested = filters.get('amount', 'All')
        if requested != 'All' and abs(float(requested) - row['amount']) >= .005:
            continue
        if without_evidence and (row.get('source_filename') or row.get('source_mime_type')):
            continue
        output.append(row)
        if row.get('request_number'):
            seen.add(row['request_number'])
    return output
