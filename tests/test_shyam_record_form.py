from streamlit.testing.v1 import AppTest


def test_shyam_form_batches_edits_and_preserves_bank_identifiers():
    app = AppTest.from_string('''
import datetime as dt
import streamlit as st
from src.shyam_record_form import record_form
values, replacement, submitted = record_form({
    'Date':dt.date(2026,10,28), 'Type':'Trip', 'Branch':'Pune',
    'Invoice No.':'INV100', 'LR No.':'LR100', 'Vehicle':'MH12AB1234',
    'Beneficiary':'Example Payee', 'Account Number':'001234', 'IFSC':'TEST0000001',
    'Revenue':1000.0, 'UPI':100.0, 'Remarks':'Original',
}, {}, 'TEST-1', ['Type'], ['Pune','Wada'])
if submitted:
    st.session_state['saved_values'] = values
''').run()
    assert not app.exception
    assert not app.get('data_editor')
    next(widget for widget in app.text_input if widget.label == 'Beneficiary').set_value('Updated Payee')
    next(widget for widget in app.number_input if widget.label == 'UPI').set_value(250)
    assert 'saved_values' not in app.session_state
    next(widget for widget in app.button if widget.label == 'Save changes').click().run()
    assert not app.exception
    saved = app.session_state['saved_values']
    assert saved['Beneficiary'] == 'Updated Payee'
    assert saved['UPI'] == 250
    assert saved['Account Number'] == '001234'
    assert saved['LR No.'] == 'LR100'
