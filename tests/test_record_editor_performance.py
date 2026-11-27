import ast
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_fragment_edit_control_opens_dialog():
    tree = ast.parse(Path('app.py').read_text())
    control = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == 'record_edit_control')
    app = AppTest.from_string('''
import streamlit as st
class Store:
    def get(self, number):
        return {'request_number':number, 'status':'Verified'}
store = Store()
st.session_state['dashboard_reads'] = st.session_state.get('dashboard_reads', 0) + 1
@st.dialog('Test record editor')
def view_record(record):
    st.write('Opened ' + record['request_number'])
''' + ast.unparse(control) + "\nrecord_edit_control({'request_number':'TEST-1'})\n").run()
    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
    # AppTest starts a full script runner per run; browser fragment routing is
    # supplied by Streamlit. Verify registration and the nested dialog here.
    assert any(isinstance(node, ast.Attribute) and node.attr == 'fragment'
               for node in control.decorator_list)
    assert any('Opened TEST-1' in item.value for item in app.markdown)


def test_records_table_includes_every_filtered_row_in_one_scroll_container():
    tree = ast.parse(Path('app.py').read_text())
    renderer = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'render_records')
    table = next(node for node in ast.walk(renderer) if isinstance(node, ast.With)
                 and any(isinstance(item.context_expr, ast.Call)
                         and any(keyword.arg == 'key' and isinstance(keyword.value, ast.Name)
                                 and keyword.value.id == 'table_key'
                                 for keyword in item.context_expr.keywords)
                         for item in node.items))
    app = AppTest.from_string('''
import datetime as dt
from contextlib import nullcontext
from html import escape
import streamlit as st
from src.access_control import FULL_DELETE_USERS, SELF_DELETE_USERS, can_delete_record
from src.branch_names import canonical_branch
from src.invoice_display import dtr_invoice_text
from src.number_format import format_inr
from src.record_filters import DIRECT_EXPENSES, TRIP_RECORDS
from src.text_normalization import canonical_vehicle_capacity
from src.vehicle_normalization import canonical_vehicle_number

current_user = 'Sid'
designed_records = True
table_key = 'sid_records_table'
record_type = TRIP_RECORDS
trip_record_count, expense_record_count = 504, 0
rows = [{'request_number': f'TEST-{i}', 'trip_date': dt.date(2026, 11, 24),
         'report_scope': 'DTR', 'created_by': 'Sid', 'invoice_number': f'INV-{i}'}
        for i in range(1, trip_record_count + 1)]
unpack = lambda value: value or {}
clean_text = lambda value: str(value or '')
as_date = lambda value: value
number = lambda value: float(value or 0)

def record_edit_control(record):
    st.button('Edit', key=f"edit-{record['request_number']}")

def confirm_record_delete(record):
    st.write(f"Confirm {record['request_number']}")
''' + ast.unparse(table)).run(timeout=20)
    assert not app.exception
    assert len([button for button in app.button if button.label == 'Edit']) == 504
    assert app.button(key='edit-TEST-51')
    assert app.button(key='delete_record_TEST-504')
    assert all(button.label in {'Edit', 'Delete'} for button in app.button)
