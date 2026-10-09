"""Exercise the actual app save translator without starting Streamlit services."""
import ast
import datetime as dt
import json
from pathlib import Path

import pandas as pd

from src.ashok_dates import parse_month_date
from src.dtr_dates import parse_dtr_date
from src.entry_finance import advance_summary
from src.request_store import RequestStore
from src.trip_dtr_report import DTR_REVIEW_COLUMNS


def translator():
    tree = ast.parse(Path('app.py').read_text())
    names = {'clean_text', 'number', 'unpack', 'dtr_record_update_values'}
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    context = dict(pd=pd, json=json, parse_month_date=parse_month_date,
                   parse_dtr_date=parse_dtr_date, advance_summary=advance_summary,
                   DTR_REVIEW_COLUMNS=DTR_REVIEW_COLUMNS, KNOWN_COMPANIES=[], KNOWN_LOCATIONS=[])
    for name in ('canonical_branch', 'canonical_company', 'canonical_vehicle_number',
                 'canonical_vehicle_capacity', 'canonical_ownership', 'canonical_location',
                 'canonical_transporter_name', 'canonical_vehicle_placer'):
        context[name] = lambda value, *args: str(value or '').strip()
    exec(compile(ast.Module(body=functions, type_ignores=[]), 'app.py', 'exec'), context)
    return context['dtr_record_update_values']


def test_ashok_dtr_save_updates_same_live_trip_and_preserves_evidence(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'records.db'}")
    request = store.create({'trip_date': dt.date(2026,9,2), 'created_by': 'Ashok',
        'vehicle_number': 'RJ09GF1234', 'transporter_name': 'Old transporter',
        'rtgs_done': True, 'source_image': b'invoice', 'source_filename': 'invoice.pdf',
        'rtgs_data': {'BENE_ACC_NO': '001234', 'BENE_IFSC': 'BANK0001234'},
        'dtr_data': {'_retained_metadata': 'keep'}})
    before = store.get(request)
    edited = {'Date': '09/02/2026', 'Branch': 'Vadodara', 'Vehicle No.': 'RJ09GF1234',
        'Transporter Name': 'New transporter', 'Benificiary Name': 'Beneficiary',
        'LR No.': 'LR123', 'Invoice No.': 'INV123', 'Review Notes': 'Reviewed',
        'Revenue': 12000, 'Transporter Freight': 10000, 'RTGS ADVANCE': 3000,
        'Cash Adv.': 500, 'UPI': 100, 'Diesel Adv.': 400, 'Billtee': 50,
        'Total Adv.': 999, 'Balance Amt.': 999}
    values = translator()(before, edited)
    store.update_many([(request, values)], 'dtr_report_editor', 'Ashok',
                      expected_versions={request: before['updated_at']})
    after = store.get(request)
    dtr, rtgs = json.loads(after['dtr_data']), json.loads(after['rtgs_data'])
    assert len(store.list()) == 1
    assert after['transporter_name'] == dtr['Transporter Name'] == 'New transporter'
    assert after['trip_date'] == dt.date(2026,9,2)
    assert after['total_advance'] == dtr['Total Adv.'] == 4050
    assert after['balance_amount'] == dtr['Balance Amt.'] == 5950
    assert after['invoice_number'] == 'INV123'
    assert dtr['LR No.'] == 'LR123' and dtr['Review Notes'] == 'Reviewed'
    assert dtr['_retained_metadata'] == 'keep'
    assert rtgs['BENE_ACC_NO'] == '001234' and rtgs['AMOUNT'] == 3000
    assert after['rtgs_done'] is True
    assert store.get_evidence(request)['source_image'] == b'invoice'


def test_other_users_keep_existing_dtr_total_behavior():
    values = translator()({'created_by': 'Ajit', 'dtr_data': {}, 'rtgs_data': {}},
                         {'Date': '2026-09-02', 'Total Adv.': 123, 'Balance Amt.': 456})
    assert values['total_advance'] == 123 and values['balance_amount'] == 456
