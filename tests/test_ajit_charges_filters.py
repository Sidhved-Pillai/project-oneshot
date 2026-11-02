import pytest
from streamlit.testing.v1 import AppTest
from tests.test_batched_interactions import trip_app
from src.pnl_report import branch_pnl_summary, vehicle_number_pnl_summary, vehicle_pnl_summary


def test_ajit_editable_diesel_and_charges_update_expense_profit():
    app = trip_app('Ajit')
    next(w for w in app.number_input if w.label == 'Revenue freight (₹)').set_value(10000).run()
    next(w for w in app.number_input if w.label == 'Transporter freight (₹)').set_value(7000).run()
    next(w for w in app.number_input if w.label == 'Halting Charges (₹)').set_value(200).run()
    next(w for w in app.number_input if w.label == 'Loading Charges (₹)').set_value(300).run()
    next(w for w in app.number_input if w.label == 'Diesel Qty (L)').set_value(20).run()
    next(w for w in app.number_input if w.label == 'Diesel (₹)').set_value(1800).run()
    assert not app.exception
    assert app.session_state['test_returned_values']['diesel_rate'] == 90
    assert next(m for m in app.metric if m.label == 'Total Expense').value == '₹7,500.00'
    assert next(m for m in app.metric if m.label == 'Profit / Loss').value == '₹2,500.00'
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
    assert any(w.label == 'Add Pumps' for w in app.text_input)
    assert not any(w.label == 'Pump Name' for w in app.selectbox)


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
