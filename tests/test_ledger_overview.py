from decimal import Decimal

from src.ledger_overview import outstanding_totals


def test_three_overview_amounts_reflect_confirmed_clearances():
    trips = [
        {'request_number': 'one', 'report_scope': 'Both', 'upi': 500,
         'dtr_data': {'Billtee': 300}},
        {'request_number': 'two', 'report_scope': 'Both', 'upi': 200,
         'dtr_data': {'Billtee': 100}},
        {'request_number': 'archived', 'report_scope': 'Both', 'upi': 999,
         'dtr_data': {'Billtee': 999}, 'is_archived': True},
    ]
    totals = outstanding_totals(trips, [{'_outstanding': Decimal('125.40')}],
        {'one': Decimal('500')}, {'two': Decimal('100')})
    assert totals == {'balance': Decimal('125.40'), 'upi': Decimal('200.00'),
                      'billtee': Decimal('300.00')}


def test_selector_and_three_cards_persist_across_modes():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
import datetime as dt
from src.pending_payments import render_pending_payments
class Store:
    def settlement_snapshot(self, user): return [], [], []
    def reimbursement_clearings(self, user, kind): return {}
    def pending_upi_profiles(self, user): return {}
    def list_upi_payments(self): return {}
    def list_billtee_payments(self): return {}
trips = [{'request_number':'REQ-1', 'created_by':'Manish', 'report_scope':'Both',
          'trip_date':dt.date(2026,11,20), 'updated_at':'version',
          'vehicle_number':'MH01TEST', 'branch':'Wada', 'upi':500,
          'dtr_data':{'Billtee':300, 'Veh Placed by':'Manish'}}]
render_pending_payments('Sid', trips, {}, {}, Store())
''').run()
    for kind in ('balance', 'upi', 'billtee'):
        app.session_state['pending_kind_card'] = kind
        app.run()
        assert not app.exception
        assert len([button for button in app.button if str(button.key).startswith('ledger_overview_')]) == 3
        markup = ' '.join(element.value for element in app.markdown)
        assert all(label in markup for label in (
            'Balance Payable To Clear', 'UPI To Clear', 'Billtee To Clear'))
        if kind == 'balance':
            assert any(button.label == 'Apply Filter' for button in app.button)
        else:
            assert not any(button.label == 'Apply Filter' for button in app.button)
