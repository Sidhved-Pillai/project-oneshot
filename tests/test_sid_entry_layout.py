from tests.test_batched_interactions import trip_app


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
    for user in ('Ajit', 'Vijay', 'Ashok', 'Manish', 'Nitish', 'Shyam'):
        app = trip_app(user)
        assert not app.exception
        assert not any('sid_' in block.proto.id for block in app.get('flex_container'))
        assert any('1. Basic information' in m.value for m in app.markdown)
