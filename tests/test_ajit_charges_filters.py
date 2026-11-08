import pytest
from streamlit.testing.v1 import AppTest
from tests.test_batched_interactions import trip_app
from src.pnl_report import branch_pnl_summary, vehicle_number_pnl_summary, vehicle_pnl_summary


@pytest.mark.parametrize('user', ['Ajit', 'Vijay', 'Ashok', 'Nitish', 'Shyam', 'Sid'])
def test_inline_diesel_details_expand_and_hide_for_every_user(user):
    app = trip_app(user)
    assert not app.exception
    assert not any(w.label in ('Diesel Rate (₹/L)', 'Diesel Qty (L)', 'Halting Charges (₹)', 'Loading Charges (₹)') for w in app.number_input)
    next(w for w in app.number_input if w.label == 'Diesel (₹)').set_value(1800).run()
    next(w for w in app.number_input if w.label == 'Diesel Rate (₹/L)').set_value(90).run()
    assert app.session_state['test_returned_values']['diesel_quantity'] == 20
    next(w for w in app.selectbox if w.label == 'Pump Name').select('Reliance').run()
    next(w for w in app.selectbox if w.label == 'Choose Cardholder Name').select('Ajit').run()
    assert app.session_state['test_returned_values']['card_name'] == 'Ajit'
    next(w for w in app.number_input if w.label == 'Diesel (₹)').set_value(0).run()
    assert not app.exception
    assert not any(w.label in ('Pump Name', 'Choose Cardholder Name') for w in app.selectbox)
    values = app.session_state['test_returned_values']
    assert values['diesel_pump_name'] == values['card_name'] == ''
    assert values['diesel_rate'] is None and values['diesel_quantity'] is None


def test_ajit_editable_diesel_and_charges_update_expense_profit():
    app = trip_app('Ajit')
    next(w for w in app.number_input if w.label == 'Revenue freight (₹)').set_value(10000).run()
    next(w for w in app.number_input if w.label == 'Transporter freight (₹)').set_value(7000).run()
    assert not any(w.label in ('Halting Charges (₹)', 'Loading Charges (₹)', 'Diesel Qty (L)') for w in app.number_input)
    next(w for w in app.number_input if w.label == 'Diesel (₹)').set_value(1800).run()
    next(w for w in app.number_input if w.label == 'Diesel Qty (L)').set_value(20).run()
    assert not app.exception
    assert app.session_state['test_returned_values']['diesel_rate'] == 90
    assert next(m for m in app.metric if m.label == 'Total Expense').value == '₹7,000.00'
    assert next(m for m in app.metric if m.label == 'Profit / Loss').value == '₹3,000.00'
    assert any(w.label == 'Pump Name' for w in app.selectbox)


@pytest.mark.parametrize('ownership,freight,diesel,expected', [('Own',0,1800,2300),('Outside',7000,0,7500)])
def test_charges_reach_both_vehicle_and_ownership_pnl(ownership, freight, diesel, expected):
    row = {'created_by':'Ajit','branch':'Pune','vehicle_number':'TEST1234','ownership_type':ownership,
           'revenue':10000,'transporter_freight':freight,'diesel_advance':diesel,
           'dtr_data':{'Halting Charges':200,'Loading Charges':300}}
    for report in (branch_pnl_summary,vehicle_number_pnl_summary):
        total = report([row],[])[-1]
        assert total['Expense'] == expected and total['Profit'] == 10000 - expected
    vertical = {item['Particular']:item['Amount'] for item in vehicle_pnl_summary([row],[],ownership)}
    assert vertical['Net Profit / (Loss)'] == 10000 - expected


def test_ashok_keeps_existing_diesel_and_pump_controls():
    app = trip_app('Ashok')
    assert not app.exception
    assert not any(w.label in ('Diesel Qty (L)','Diesel Rate (₹/L)','Halting Charges (₹)','Loading Charges (₹)') for w in app.number_input)
    next(w for w in app.number_input if w.label == 'Diesel (₹)').set_value(500).run()
    assert not app.exception
    assert any(w.label == 'Pump Name' for w in app.selectbox)
    assert any(w.label == 'Diesel Qty (L)' for w in app.number_input)


def test_pending_suggestions_and_date_range_filter_trips_chronologically():
    app = AppTest.from_string('''
import streamlit as st
import datetime as dt
from src.pending_payments import render_pending_payments
class Store:
    def pending_upi_profiles(self,user): return {}
trips = [{'request_number':str(i),'trip_date':dt.date(2026,10,day),'updated_at':'v',
          'transporter_name':'Sai Transporter','balance_amount':100,'ownership_type':'Outside',
          'rtgs_data':{'BNF_NAME':'Example','BENE_ACC_NO':'00123','BENE_IFSC':'TEST0000001'}}
         for i,day in enumerate([20,5,15])]
render_pending_payments('Sid',trips,{}, {},Store())
''').run()
    assert not app.exception
    search = next(w for w in app.selectbox if w.label == 'Search transporter / payer')
    assert 'Sai Transporter' in search.options
    search.select('Sai Transporter').run()
    import datetime as dt
    next(w for w in app.date_input if w.label == 'Trips from').set_value(dt.date(2026,10,10)).run()
    next(w for w in app.date_input if w.label == 'Trips to').set_value(dt.date(2026,10,20)).run()
    next(w for w in app.button if str(w.key).startswith('pending_expand_')).click().run()
    assert not app.exception
    frame = app.dataframe[0].value
    assert list(frame['Record']) == ['2','0']
