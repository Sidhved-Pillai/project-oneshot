import datetime as dt

from streamlit.testing.v1 import AppTest
from src.expense_date import remember_expense_date, seed_expense_date
from src.expense_review import apply_evidence_date, expense_category_increase


def test_uploaded_expense_date_replaces_remembered_date_without_changing_next_entry_preference():
    state = {}
    remember_expense_date(state, 'Nikhat', dt.date(2026, 11, 2))
    seed_expense_date(state, 'Nikhat', 'expense_1')
    apply_evidence_date(state, 'expense_1', '31-Oct-2026')
    assert state['expense_1_date'] == dt.date(2026, 10, 31)
    assert state['nikhat_last_expense_date'] == dt.date(2026, 11, 2)
    apply_evidence_date(state, 'expense_1', '')
    assert state['expense_1_date'] is None
    apply_evidence_date(state, 'expense_1', '2024-10-31')
    assert state['expense_1_date'] is None


def test_evidence_date_preserves_an_explicit_manual_selection():
    state = {'expense_1_date': dt.date(2026, 10, 30), 'expense_1_date_manual': True}
    apply_evidence_date(state, 'expense_1', '2026-11-02')
    assert state['expense_1_date'] == dt.date(2026, 10, 30)


def test_reclassification_does_not_silently_keep_old_amount():
    before = {'categories': {'Extra Expense': 1650, 'Repair and maintenance': 0}}
    assert expense_category_increase(before, {'categories': {'Extra Expense': 1650, 'Repair and maintenance': 1650}})
    assert not expense_category_increase(before, {'categories': {'Extra Expense': 0, 'Repair and maintenance': 1650}})
    assert not expense_category_increase(before, {'categories': {'Extra Expense': 1700}})


def form():
    return AppTest.from_string('''
import streamlit as st
from src.shyam_record_form import record_form
values, _, saved = record_form({'Type':'Direct expense','Extra Expense':1650.0,
    'Repair and maintenance':0.0,'Remarks':''}, {}, 'RECLASS', ['Type'], [])
if saved:
    st.session_state['saved'] = values
''').run()


def test_form_requires_confirmation_for_extra_category_but_allows_legitimate_split():
    app = form()
    assert not app.exception
    next(w for w in app.number_input if w.label == 'Repair and maintenance').set_value(1650)
    next(w for w in app.button if w.label == 'Save changes').click().run()
    assert not app.exception
    assert 'saved' not in app.session_state
    assert app.warning
    app.checkbox[0].check()
    next(w for w in app.button if w.label == 'Save changes').click().run()
    assert not app.exception
    assert app.session_state['saved']['Repair and maintenance'] == 1650
    assert app.session_state['saved']['Extra Expense'] == 1650


def test_form_allows_transfer_on_first_save_without_extra_confirmation():
    app = form()
    next(w for w in app.number_input if w.label == 'Repair and maintenance').set_value(1650)
    next(w for w in app.number_input if w.label == 'Extra Expense').set_value(0)
    next(w for w in app.button if w.label == 'Save changes').click().run()
    assert not app.exception
    assert app.session_state['saved']['Extra Expense'] == 0
    assert not app.checkbox
