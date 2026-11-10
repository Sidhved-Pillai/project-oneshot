import ast
import datetime as dt
import json
import re
from pathlib import Path
from src.expense_duplicates import expense_duplicate_signature
from src.records_store_v27 import RequestStore
from src.pnl_report import branch_pnl_summary


def duplicate_review(rows):
    function = next(node for node in ast.parse(Path('app.py').read_text()).body
                    if isinstance(node, ast.FunctionDef) and node.name == 'duplicate_records')
    scope = {'re':re, 'clean_text':lambda value:str(value or '').strip(), 'as_date':lambda value:value,
             'number':lambda value:float(value or 0), 'unpack':lambda value:json.loads(value) if isinstance(value,str) else (value or {}),
             'expense_duplicate_signature':expense_duplicate_signature}
    exec(compile(ast.Module(body=[function],type_ignores=[]),'duplicate_review','exec'),scope)
    return scope['duplicate_records'](rows)


def rent(payee, **changes):
    return {'report_scope':'Expense', 'trip_date':dt.date(2026,11,1), 'branch':'Vadodara',
            'created_by':'Nikhat', 'vehicle_number':'', 'beneficiary_name':payee, 'amount':15000, 'expense_type':'Rent',
            'dtr_data':{'categories':{'Rent':15000}}, 'status':'Verified', **changes}


def test_separate_offices_same_date_and_amount_are_saved_and_summed(tmp_path):
    store = RequestStore(f'sqlite:///{tmp_path / "rent.db"}')
    ids = [store.create(rent(payee)) for payee in ('Office One Landlord', 'Office Two Landlord')]
    rows = [store.get(number) for number in ids]
    assert len(store.list()) == 2
    assert duplicate_review(rows) == []
    report = branch_pnl_summary([], [{**row,'categories':{'Rent':15000}} for row in rows])
    assert next(row['Rent'] for row in report if row['Branch'] == 'Vadodara') == 30000
    assert next(row['Rent'] for row in report if row['Branch'] == 'Total') == 30000


def test_expense_duplicates_require_matching_payee_branch_categories_and_bank():
    base = rent('Office Landlord', id=1)
    rows = [base,
            {**base,'id':2,'branch':'Pune'},
            {**base,'id':3,'beneficiary_name':'Other Landlord'},
            {**base,'id':4,'dtr_data':{'categories':{'Salary':15000}}},
            {**base,'id':5,'rtgs_data':{'BENE_ACC_NO':'000123'}},
            {**base,'id':6,'notes':'Second office'},
            {**base,'id':7,'created_at':'later','request_number':'copy'}]
    assert duplicate_review(rows) == [rows[-1]]
