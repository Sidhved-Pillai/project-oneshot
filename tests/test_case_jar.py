import datetime as dt

from src.case_jar import case_jar_totals
from src.ai_intake import UnifiedIntakeRow, merge_same_trip_intake_rows
from tests.test_batched_interactions import trip_app
from tests.test_photo_autofill import functions as autofill_functions


def test_kill_bill_rules_classify_20_ltr_and_sum_printed_quantities():
    assert case_jar_totals([
        {'description':'Bisleri Water 200ML 48 MRP', 'qty':'60.00'},
        {'description':'Bisleri Water 500ML', 'qty':240},
        {'description':'Bisleri Water 1.0LTR', 'qty':215},
        {'description':'Bisleri Water 20 LTR', 'qty':'50.00'},
        {'description':'Bisleri 20-LTR', 'quantity':'1,000'},
        {'description':'Bisleri 20.LTR', 'qty':10},
    ]) == (515, 1060)
    assert case_jar_totals([{'description':'Bisleri 20 LTR','qty':20}]) == (0,20)
    assert case_jar_totals([{'description':'Bisleri 200LTR','qty':12}]) == (12,0)
    assert case_jar_totals([]) == (None,None)
    assert case_jar_totals([{'description':'Water','qty':None}]) == (None,None)


def test_multiple_vijay_invoices_keep_every_product_row_once():
    rows = [UnifiedIntakeRow(invoice_number='MUMCIN270000001', items=[{'description':'Water 20 LTR','qty':10}]),
            UnifiedIntakeRow(invoice_number='MUMCIN270000002', items=[{'description':'Water 500ML','qty':30}])]
    merged = merge_same_trip_intake_rows(rows)
    assert len(merged.items) == 2
    assert case_jar_totals(merged.items) == (30,10)
    assert len(rows[0].items) == 1


def test_vijay_case_jar_fields_are_optional_and_other_logins_unchanged():
    app = trip_app('Vijay')
    assert not app.exception
    assert app.session_state['test_returned_values']['cases'] is None
    assert app.session_state['test_returned_values']['jars'] is None
    next(w for w in app.number_input if w.label == 'Case').set_value(250).run()
    assert not app.exception
    assert app.session_state['test_returned_values']['cases'] == 250
    other = trip_app('Nitish')
    assert not any(w.label in ('Case','Jar') for w in other.number_input)


def test_ajit_case_jar_fields_match_vijay_position_and_accept_values():
    app = trip_app('Ajit')
    assert not app.exception
    labels = [w.label for w in app.number_input]
    assert labels.index('Case') < labels.index('Jar')
    assert app.session_state['test_returned_values']['cases'] is None
    assert app.session_state['test_returned_values']['jars'] is None
    next(w for w in app.number_input if w.label == 'Case').set_value(42).run()
    next(w for w in app.number_input if w.label == 'Jar').set_value(8).run()
    assert not app.exception
    assert app.session_state['test_returned_values']['cases'] == 42
    assert app.session_state['test_returned_values']['jars'] == 8


def test_ajit_invoice_rows_autofill_case_jar_without_vijay_invoice_rules():
    row = UnifiedIntakeRow(date='2026-11-20', invoice_number='AJIT-123', items=[
        {'description': 'Water 500ML', 'qty': 42},
        {'description': 'Water 20 LTR', 'qty': 8},
    ])
    scope, state = autofill_functions(lambda *args: (type('Result', (), {'rows': [row]})(), None))
    scope['current_user'] = 'Ajit'
    scope['case_jar_totals'] = case_jar_totals
    scope['as_date'] = dt.date.fromisoformat
    scope['OPERATIONS_START'] = dt.date(2026, 1, 1)
    scope['autofill']([{'filename': 'invoice.jpg', 'mime_type': 'image/jpeg', 'data': b'test'}], '', 'trip_0')
    assert state['trip_0_cases'] == 42
    assert state['trip_0_jars'] == 8
    assert state['trip_0_invoice_number'] == 'AJIT-123'
