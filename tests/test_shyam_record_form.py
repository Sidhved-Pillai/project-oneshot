from streamlit.testing.v1 import AppTest


def test_invoice_is_loaded_only_after_view_invoice_click():
    app = AppTest.from_string('''
import streamlit as st
from src.shyam_record_form import record_form
def load():
    st.session_state['evidence_reads'] = st.session_state.get('evidence_reads', 0) + 1
    return {}
record_form({'Beneficiary':'Example','Remarks':''}, {}, 'LAZY-1', [], ['Pune'], load_evidence=load)
''').run()
    assert not app.exception
    assert 'evidence_reads' not in app.session_state
    next(widget for widget in app.button if widget.label == 'View Invoice').click().run()
    assert not app.exception
    assert app.session_state['evidence_reads'] == 1


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


def test_empty_vehicle_editor_only_shows_required_trip_fields():
    app = AppTest.from_string('''
import datetime as dt
from src.shyam_record_form import record_form
record_form({'Date':dt.date(2026,11,24),'Company':'Empty Vehicle',
    'Vehicle':'MH04AB1234','From':'Pune','To':'Wada','Branch':'',
    'Invoice No.':'','Remarks':''}, {}, 'EMPTY-1', ['Company'], ['Pune'],
    companies=['', 'Empty Vehicle'])
''').run()
    assert not app.exception
    assert {widget.label for widget in app.text_input} == {'Vehicle', 'From', 'To'}
    assert not any(widget.label == 'View Invoice' for widget in app.button)


def test_ambiguous_saint_gobain_requires_business_selection():
    app = AppTest.from_string('''
from src.shyam_record_form import record_form
record_form({'Company':'Saint-Gobain India Private Limited','Remarks':''}, {},
    'SG-1', [], ['Pune'], companies=['', 'Saint Gobain - Gyproc', 'Saint Gobain - Weber'],
    review_company=True)
''').run()
    assert not app.exception
    company = next(widget for widget in app.selectbox if widget.label == 'Company')
    assert company.options == ['', 'Saint Gobain - Gyproc', 'Saint Gobain - Weber']
    assert next(widget for widget in app.button if widget.label == 'Save changes').disabled
