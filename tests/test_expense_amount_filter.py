import datetime as dt
from decimal import Decimal
from streamlit.testing.v1 import AppTest
from src.expense_amounts import expense_amounts
from src.record_filters import filter_direct_expenses


def test_options_and_filter_use_same_saved_expense_amounts():
    row={'report_scope':'Expense','amount':9999,'status':'Verified',
         'dtr_data':{'categories':{'Salary':500,'Rent':200}}}
    assert expense_amounts(row)=={Decimal('500'),Decimal('200'),Decimal('700')}
    assert filter_direct_expenses([row],500)==[row]
    assert filter_direct_expenses([row],'₹500')==[]
    assert filter_direct_expenses([row],'500.00')==[row]
    assert filter_direct_expenses([row],700)==[row]
    assert filter_direct_expenses([row],9999)==[]
    assert expense_amounts({**row,'status':'Cancelled'})==set()
    assert expense_amounts({**row,'is_archived':True})==set()
    assert expense_amounts({'report_scope':'DTR','amount':500})==set()
    assert expense_amounts({'report_scope':'Expense','amount':0})==set()


def test_dropdown_excludes_trip_costs_and_apply_returns_matching_expense():
    app=AppTest.from_string('''
import datetime as dt
import streamlit as st
from src.batched_records_v7 import render_filters
from src.record_filters import filter_direct_expenses
rows=[{'report_scope':'Expense','amount':500,'trip_date':dt.date(2026,11,12),
       'dtr_data':{},'vehicle_number':''},
      {'report_scope':'DTR','amount':11.8,'upi':41.3,'ownership_type':'Own','dtr_data':{}}]
st.session_state.setdefault('applied_records_filters_Nikhat',{'record_type':'Direct Expenses'})
f=render_filters(rows,'Nikhat',dt.date(2026,11,12))
matched=filter_direct_expenses([rows[0]],None if f['amount']=='All' else f['amount'])
st.session_state['matches']=len(matched)
''').run()
    assert not app.exception
    amount=next(w for w in app.selectbox if w.label=='By Amount')
    assert amount.options==['All','₹500.00']
    amount.select(500)
    next(w for w in app.button if w.label=='Apply Filters').click().run()
    assert not app.exception
    assert app.session_state['matches']==1
