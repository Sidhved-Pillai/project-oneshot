import datetime as dt
from io import BytesIO
import json
import pytest
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest
from src.records_store_v28 import RequestStore
from src.records_export_v2 import export_records_excel
from src.record_integrity import can_edit_record
from src.record_filters import filter_direct_expenses
from src.pnl_report import branch_pnl_summary


def expense(store):
    return store.create({'report_scope':'Expense', 'trip_date':dt.date(2026,10,18),
        'vehicle_number':'', 'branch':'Wada', 'created_by':'Nikhat', 'amount':2000,
        'expense_type':"Driver's salary", 'dtr_data':{'categories':{"Driver's salary":2000}},
        'status':'Verified'})


def test_recategorization_updates_filter_export_and_pnl(tmp_path):
    store = RequestStore(f'sqlite:///{tmp_path / "edits.db"}')
    number = expense(store)
    before = store.get(number)
    store.update(number, {'dtr_data':{'categories':{'Salary':2000,"Driver's salary":0}}},
                 'records_tab','Shyam', expected_version=before['updated_at'])
    row = store.get(number)
    assert row['created_by'] == 'Nikhat'
    assert row['expense_type'] == 'Salary' and row['amount'] == 2000
    assert filter_direct_expenses([row], heading='Salary') == [row]
    assert filter_direct_expenses([row], heading="Driver's salary") == []
    # Existing rows with a stale heading must export correctly as well.
    sheet = load_workbook(BytesIO(export_records_excel([{**row,'expense_type':"Driver's salary"}], True))).active
    values = dict(zip([cell.value for cell in sheet[1]], [cell.value for cell in sheet[2]]))
    assert values['Expense Heading'] == 'Salary' and values['Amount'] == 2000
    report = branch_pnl_summary([], [{**row,'categories':json.loads(row['dtr_data'])['categories']}])
    wada = next(item for item in report if item['Branch'] == 'Wada')
    assert wada['Salary'] == 2000 and wada["Driver's Salary"] == 0


def test_stale_edit_cannot_erase_another_users_changes(tmp_path):
    store = RequestStore(f'sqlite:///{tmp_path / "concurrency.db"}')
    number = expense(store)
    version = store.get(number)['updated_at']
    store.update(number, {'notes':'Latest edit'}, 'records_tab','Nikhat', expected_version=version)
    with pytest.raises(ValueError, match='changed while'):
        store.update(number, {'notes':'Old edit'}, 'records_tab','Shyam', expected_version=version)
    assert store.get(number)['notes'] == 'Latest edit'


@pytest.mark.parametrize('user', ['Nikhat','Shyam','Ajit','Sid'])
def test_authorized_editors_can_edit_any_creator(user):
    assert all(can_edit_record(user, {'created_by':creator}) for creator in ('Ashok','Vijay','Manish','Nikhat'))


def test_other_users_can_edit_their_own_records_only():
    assert can_edit_record('Ashok',{'created_by':'Ashok'})
    assert not can_edit_record('Ashok',{'created_by':'Nitish'})


def test_records_form_allows_previous_month_date():
    app = AppTest.from_string('''
import datetime as dt
import streamlit as st
from src.record_form_v5 import record_form
values, _, saved = record_form({'Date':dt.date(2026,11,10),'Remarks':''}, {}, 'DATES', [], ['Wada'])
if saved: st.session_state['saved_date'] = values['Date']
''').run()
    app.date_input[0].set_value(dt.date(2026,10,18))
    next(button for button in app.button if button.label == 'Save changes').click().run()
    assert not app.exception
    assert app.session_state['saved_date'] == dt.date(2026,10,18)
