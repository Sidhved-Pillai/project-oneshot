import ast
from pathlib import Path
from streamlit.testing.v1 import AppTest
from src.expense_autofill import expense_suggestions


def test_expense_profiles_include_trips_and_expenses_and_keep_latest_bank_pair():
    rows = [
        {'id':1,'status':'Verified','beneficiary_name':'Test Name','vehicle_number':'MH12AB1234',
         'rtgs_data':{'BENE_ACC_NO':'00111','BENE_IFSC':'OLD0000001'}},
        {'id':2,'status':'Verified','report_scope':'Expense','beneficiary_name':'Test Name',
         'rtgs_data':'{"BENE_ACC_NO":"00222","BENE_IFSC":"NEW0000001"}'},
        {'id':3,'status':'Cancelled','beneficiary_name':'Bad Name'},
    ]
    profiles, names, vehicles = expense_suggestions(rows)
    assert names == ['Test Name'] and vehicles == ['MH12AB1234']
    assert profiles['TESTNAME'] == {'account':'00222','ifsc':'NEW0000001'}


def test_selecting_expense_beneficiary_autofills_and_switching_clears_stale_bank():
    app = AppTest.from_string('''
import streamlit as st
from src.expense_autofill import expense_identity_inputs
rows=[{'status':'Verified','beneficiary_name':'Known','vehicle_number':'MH12AB1234',
       'rtgs_data':{'BENE_ACC_NO':'000123','BENE_IFSC':'TEST0000001'}},
      {'status':'Verified','beneficiary_name':'Unknown','vehicle_number':'MH14CD5678'}]
a,b=st.columns(2)
expense_identity_inputs('expense_0',a,b,rows)
st.text_input('Account',key='expense_0_bank_account')
st.text_input('IFSC',key='expense_0_ifsc')
''').run()
    app.selectbox[0].select('Known').run()
    assert not app.exception
    assert app.text_input[0].value == '000123'
    assert app.text_input[1].value == 'TEST0000001'
    assert app.selectbox[1].options == ['', 'MH12AB1234', 'MH14CD5678']
    app.selectbox[0].select('Unknown').run()
    assert not app.exception
    assert app.text_input[0].value == app.text_input[1].value == ''


def test_duplicate_selections_are_batched_and_number_function_not_shadowed():
    component = Path('src/dashboard_duplicates_component/index.html').read_text()
    assert "selected.add(box.dataset.id)" in component
    assert "numbers:[...selected]" in component
    # Checkbox changes stay in the browser; only Delete Selected sends a mutation.
    checkbox_handler = component.split("box.onchange=()=>",1)[1].split("document.querySelector('.cancel')",1)[0]
    assert 'emit(' not in checkbox_handler
    tree = ast.parse(Path('app.py').read_text())
    assert not any(isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='number'
                   for n in tree.body for n in ast.walk(n) if not isinstance(n,ast.FunctionDef))
