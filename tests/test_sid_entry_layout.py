from tests.test_batched_interactions import trip_app
import pytest


def test_sid_preview_uses_cards_and_preserves_payment_and_fuel_rules():
    app = trip_app('Sid')
    assert not app.exception
    keys = {block.proto.id.split('-')[-1] for block in app.get('flex_container') if block.proto.id}
    assert {'sid_basic_panel', 'sid_vehicle_panel', 'sid_beneficiary_panel', 'sid_payment_panel'} <= keys
    next(w for w in app.number_input if w.label == 'Transporter freight (₹)').set_value(5000).run()
    next(w for w in app.number_input if w.label == 'Diesel (₹)').set_value(1800).run()
    next(w for w in app.number_input if w.label == 'Diesel Rate (₹/L)').set_value(90).run()
    next(w for w in app.selectbox if w.label == 'Pump Name').select('Reliance').run()
    next(w for w in app.selectbox if w.label == 'Choose Cardholder Name').select('Ajit').run()
    next(w for w in app.number_input if w.label == 'UPI (₹)').set_value(200).run()
    assert not app.exception
    values = app.session_state['test_returned_values']
    assert values['diesel_quantity'] == 20
    assert values['card_name'] == 'Ajit'
    assert next(m for m in app.metric if m.label == 'Total advance').value == '₹2,000.00'
    assert next(m for m in app.metric if m.label == 'Balance payable').value == '₹3,000.00'


def test_other_members_keep_their_original_layout():
    for user in ('Shyam',):
        app = trip_app(user)
        assert not app.exception
        assert not any('sid_' in block.proto.id for block in app.get('flex_container'))
        assert any('1. Basic information' in m.value for m in app.markdown)


def test_vijay_compact_layout_preserves_own_vehicle_fields_and_totals():
    app = trip_app('Vijay')
    assert not app.exception
    assert any('sid_basic_panel' in b.proto.id for b in app.get('flex_container'))
    assert next(w for w in app.selectbox if w.label == 'Own or outside').value == 'Own'
    assert {'Case', 'Jar'} <= {w.label for w in app.number_input}
    assert 'Transporter freight (₹)' not in {w.label for w in app.number_input}
    next(w for w in app.selectbox if w.label == 'Revenue freight (₹)').select(3844).run()
    next(w for w in app.number_input if w.label == 'Diesel (₹)').set_value(1800).run()
    next(w for w in app.number_input if w.label == 'Toll Expense (₹)').set_value(100).run()
    assert not app.exception
    assert next(m for m in app.metric if m.label == 'Total Expense').value == '₹1,900.00'
    assert any('₹1,944.00' in m.value for m in app.markdown)


def test_ajit_compact_layout_keeps_outside_and_own_payment_rules():
    app = trip_app('Ajit')
    assert not app.exception
    assert any('sid_basic_panel' in b.proto.id for b in app.get('flex_container'))
    next(w for w in app.number_input if w.label == 'Transporter freight (₹)').set_value(5000).run()
    next(w for w in app.number_input if w.label == 'Diesel (₹)').set_value(1800).run()
    next(w for w in app.number_input if w.label == 'Diesel Rate (₹/L)').set_value(90).run()
    assert not app.exception
    assert app.session_state['test_returned_values']['diesel_quantity'] == 20
    assert next(m for m in app.metric if m.label == 'Balance payable').value == '₹3,200.00'
    assert 'Transporter freight' not in {m.label for m in app.metric}
    assert {'Total advance', 'Balance payable', 'Total Expense', 'Profit / Loss'} <= {m.label for m in app.metric}
    assert any('ajit_payment_totals' in b.proto.id for b in app.get('flex_container'))
    next(w for w in app.selectbox if w.label == 'Own or outside').select('Own').run()
    next(w for w in app.number_input if w.label == 'Revenue freight (₹)').set_value(10000).run()
    next(w for w in app.number_input if w.label == 'Toll Expense (₹)').set_value(100).run()
    assert not app.exception
    assert next(m for m in app.metric if m.label == 'Total expense').value == '₹1,900.00'
    assert any('₹8,100.00' in m.value for m in app.markdown)
    assert not any(w.label in ('Halting Charges (₹)', 'Loading Charges (₹)') for w in app.number_input)


def test_manish_responsive_layout_preserves_driver_and_expense_workflow():
    app = trip_app('Manish')
    assert not app.exception
    assert any('sid_basic_panel' in b.proto.id for b in app.get('flex_container'))
    assert any(w.label == 'Driver name' for w in app.text_input)
    assert 'Transporter freight (₹)' not in {w.label for w in app.number_input}
    next(w for w in app.number_input if w.label == 'Revenue freight (₹)').set_value(10000).run()
    next(w for w in app.number_input if w.label == 'Diesel (₹)').set_value(1800).run()
    next(w for w in app.number_input if w.label == 'Diesel Rate (₹/L)').set_value(90).run()
    next(w for w in app.number_input if w.label == 'Route Expense (UPI) (₹)').set_value(200).run()
    next(w for w in app.number_input if w.label == 'Toll Expense (₹)').set_value(100).run()
    assert not app.exception
    assert app.session_state['test_returned_values']['diesel_quantity'] == 20
    assert next(m for m in app.metric if m.label == 'Total expense').value == '₹2,100.00'
    assert any('₹7,900.00' in m.value for m in app.markdown)


@pytest.mark.parametrize('user', ['Gopal', 'Nitish', 'Ashok'])
def test_branch_members_responsive_layout_keeps_payment_and_fuel_rules(user):
    app = trip_app(user)
    assert not app.exception
    assert any('sid_basic_panel' in b.proto.id for b in app.get('flex_container'))
    assert {'Transporter name', 'Beneficiary name'} <= {w.label for w in app.selectbox}
    assert not any(w.label == 'Driver name' for w in app.text_input)
    next(w for w in app.number_input if w.label == 'Transporter freight (₹)').set_value(5000).run()
    next(w for w in app.number_input if w.label == 'Diesel (₹)').set_value(1800).run()
    next(w for w in app.number_input if w.label == 'Diesel Rate (₹/L)').set_value(90).run()
    next(w for w in app.selectbox if w.label == 'Pump Name').select('IOCL').run()
    next(w for w in app.selectbox if w.label == 'Choose Cardholder Name').select('Nitish').run()
    next(w for w in app.number_input if w.label == 'UPI (₹)').set_value(200).run()
    assert not app.exception
    values = app.session_state['test_returned_values']
    assert values['diesel_quantity'] == 20 and values['card_name'] == 'Nitish'
    assert next(m for m in app.metric if m.label == 'Total advance').value == '₹2,000.00'
    assert next(m for m in app.metric if m.label == 'Balance payable').value == '₹3,000.00'
