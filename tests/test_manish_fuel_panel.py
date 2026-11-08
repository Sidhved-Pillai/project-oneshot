from tests.test_batched_interactions import trip_app


def test_manish_fuel_order_and_calculated_amount_update_expense():
    app = trip_app('Manish')
    assert not app.exception
    labels = [widget.label for widget in app.number_input]
    assert labels.index('Diesel Rate (₹/L)') < labels.index('Diesel Qty (L)') < labels.index('Diesel (₹)')
    next(widget for widget in app.number_input if widget.label == 'Revenue freight (₹)').set_value(11400).run()
    next(widget for widget in app.number_input if widget.label == 'Diesel Rate (₹/L)').set_value(98.18).run()
    next(widget for widget in app.number_input if widget.label == 'Diesel Qty (L)').set_value(100).run()
    assert not app.exception
    amount = next(widget for widget in app.number_input if widget.label == 'Diesel (₹)')
    assert amount.disabled and amount.value == 9818
    assert app.session_state['test_returned_values']['diesel_advance'] == 9818
    next(widget for widget in app.number_input if widget.label == 'Diesel Qty (L)').set_value(1.02).run()
    assert app.session_state['test_returned_values']['diesel_advance'] == 100.14
    next(widget for widget in app.selectbox if widget.label == 'Pump Name').select('Reliance').run()
    assert any(widget.label == 'Choose Cardholder Name' for widget in app.selectbox)
    assert not app.exception


def test_ajit_keeps_existing_editable_diesel_amount():
    app = trip_app('Ajit')
    diesel = next(widget for widget in app.number_input if widget.label == 'Diesel (₹)')
    assert not diesel.disabled
