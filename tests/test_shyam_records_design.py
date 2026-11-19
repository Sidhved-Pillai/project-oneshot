"""Exercise Shyam's batched filters, including expense switching and reset."""
from streamlit.testing.v1 import AppTest


def test_shyam_filters_submit_and_reset():
    app = AppTest.from_string('''
import datetime as dt
import streamlit as st
from src.batched_records import render_filters
rows = [dict(report_scope='Expense', amount=500, vehicle_number='MH04AB1234',
             dtr_data={'Salary':500, 'Veh Placed by':'Shyam'})]
result = render_filters(rows, 'Shyam', dt.date(2026,11,19))
st.json(result, expanded=False)
''').run()
    assert not app.exception
    next(w for w in app.selectbox if w.label == 'Record Type').select('Direct Expenses')
    next(w for w in app.button if w.label == 'Apply Filters').click().run()
    assert not app.exception
    assert any(w.label == 'By Amount' for w in app.selectbox)
    next(w for w in app.selectbox if w.label == 'By Amount').select(500.0)
    next(w for w in app.button if w.label == 'Apply Filters').click().run()
    assert app.session_state['applied_records_filters_Shyam']['amount'] == 500
    next(w for w in app.button if w.label == 'Reset').click().run()
    assert not app.exception
    assert app.session_state['applied_records_filters_Shyam']['record_type'] == 'Trip Records'
