import copy
import datetime as dt
from io import BytesIO
import json

from openpyxl import load_workbook
from src.expense_excel_layout import DIRECT_EXPENSE_EXPORT_COLUMNS
from src.records_export import export_records_excel, RECORD_EXPORT_COLUMNS


def read(records, direct=True):
    sheet = load_workbook(BytesIO(export_records_excel(records, direct))).active
    columns = [c.value for c in sheet[1]]
    return sheet, columns, [dict(zip(columns, row)) for row in sheet.iter_rows(min_row=2, values_only=True)]


def expense(categories, **extra):
    return {'report_scope':'Expense','trip_date':dt.date(2026,10,31),'created_by':'Nikhat',
            'branch':'Andheri','beneficiary_name':'Test Payee','ownership_type':'Own',
            'vehicle_number':'MH12AB1234','vehicle_type':'10 MT','amount':99999,
            'expense_type':'Old stale heading','dtr_data':json.dumps({'categories':categories,'Diesel Rate':90}),
            'rtgs_data':{'BENE_ACC_NO':'001234567890','BENE_IFSC':'TEST0000001'},
            'diesel_advance':900,'diesel_quantity':10,'total_advance':1500,
            'payment_mode':'Diesel, RTGS','notes':'Original remarks',**extra}


def test_compact_columns_match_sample_and_preserve_bank_text_and_numeric_amounts():
    sheet, columns, rows = read([expense({'Interest':68787})])
    assert columns == DIRECT_EXPENSE_EXPORT_COLUMNS
    assert len(columns) == 17 and len(set(columns)) == 17
    assert rows[0]['Amount'] == 68787 and rows[0]['Expense Heading'] == 'Interest'
    assert rows[0]['Account Number'] == '001234567890'
    assert rows[0]['Diesel Qty'] == 10 and rows[0]['Diesel Rate'] == 90
    assert rows[0]['Remarks'] == 'Original remarks'
    assert sheet.freeze_panes == 'A2' and sheet.auto_filter.ref == 'A1:Q2'
    assert sheet.cell(2,2).number_format == '#,##0.00'
    assert not {'Record','Status','Invoice Number','Salary','Route expense'} & set(columns)


def test_route_combinations_split_into_one_filter_heading_and_totals_are_not_repeated():
    records = [expense({'Route expense':100}),
               expense({'Route expense':200,'Office & General expenses':300}),
               expense({'Route expense':400,'Repair and maintenance':500})]
    original = copy.deepcopy(records)
    _, _, rows = read(records)
    headings = {r['Expense Heading'] for r in rows}
    assert headings == {'Route expense','Office & General expenses','Repair and maintenance'}
    assert sum(r['Amount'] for r in rows if r['Expense Heading']=='Route expense') == 700
    assert sum(r['Amount'] for r in rows) == 1500
    assert sum(r['Total Advance'] or 0 for r in rows) == 4500
    assert sum(r['Diesel'] or 0 for r in rows) == 2700
    assert records == original


def test_route_spelling_aliases_share_one_heading_without_losing_amounts():
    _, _, rows = read([expense({'Route Expense':100,' Route expense ':200,'Route Expense (UPI)':50})])
    assert len(rows)==1 and rows[0]['Expense Heading']=='Route expense' and rows[0]['Amount']==350


def test_legacy_records_without_categories_and_general_export_are_preserved():
    record = expense({}, amount=123, expense_type='Rent', dtr_data='{}')
    _, _, rows = read([record])
    assert rows[0]['Expense Heading']=='Rent' and rows[0]['Amount']==123
    _, columns, rows = read([record],False)
    assert columns == RECORD_EXPORT_COLUMNS and len(rows)==1
