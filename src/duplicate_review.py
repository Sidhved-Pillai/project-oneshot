"""Read-only duplicate details with an editable deletion selection column."""
import json
import pandas as pd


def duplicate_review_frame(rows):
    records = []
    for row in rows:
        raw = row.get('dtr_data') or {}
        data = json.loads(raw) if isinstance(raw, str) else raw
        records.append({
            'Select': False, 'Record ID': row['request_number'], 'Date': row.get('trip_date'),
            'Type': 'Direct Expense' if row.get('report_scope') == 'Expense' else 'Trip',
            'Branch': row.get('branch') or '', 'Vehicle': row.get('vehicle_number') or '',
            'Placed by': data.get('Veh Placed by') or row.get('created_by') or '',
            'LR No.': data.get('LR No.') or '', 'Invoice No.': row.get('invoice_number') or '',
            'From': row.get('from_location') or '', 'To': row.get('to_location') or '',
            'Revenue': float(row.get('revenue') or 0), 'Amount': float(row.get('amount') or 0),
            'Billtee': float(data.get('Billtee') or 0), 'Remarks': row.get('notes') or '',
        })
    return pd.DataFrame(records)


def selected_duplicate_numbers(frame, allowed_numbers):
    allowed = set(allowed_numbers)
    return list(dict.fromkeys(str(row['Record ID']) for _, row in frame.iterrows()
                             if row['Select'] == True and row['Record ID'] in allowed))
