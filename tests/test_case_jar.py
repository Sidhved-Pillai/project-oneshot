from src.case_jar import case_jar_totals
from src.ai_intake import UnifiedIntakeRow, merge_same_trip_intake_rows
from tests.test_batched_interactions import trip_app


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
