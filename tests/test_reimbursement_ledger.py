import datetime as dt

import pytest

from src.request_store import RequestStore
from src.reimbursement_ledger_ui import reimbursement_groups


def trip(store, creator='Manish', upi=500, billtee=300):
    return store.create({
        'created_by': creator, 'report_scope': 'Both', 'trip_date': dt.date(2026, 11, 20),
        'vehicle_number': 'MH01TEST', 'branch': 'Wada', 'upi': upi,
        'dtr_data': {'Billtee': billtee, 'Veh Placed by': creator},
    })


@pytest.mark.parametrize('kind', ['upi', 'billtee'])
def test_selected_reimbursements_clear_without_changing_trip_costs(tmp_path, kind):
    store = RequestStore(f'sqlite:///{tmp_path / "ledger.db"}')
    numbers = [trip(store), trip(store)]
    before = {number: store.get(number) for number in numbers}
    selected = {number: before[number]['updated_at'] for number in numbers}
    assert store.clear_reimbursements('Sid', kind, selected) == 2
    clearings = store.reimbursement_clearings('Sid', kind)
    assert set(clearings) == set(numbers)
    assert all(clearings[number] == (500 if kind == 'upi' else 300) for number in numbers)
    assert {number: store.get(number) for number in numbers} == before
    groups = reimbursement_groups(list(before.values()), kind, {}, {}, clearings)
    assert all(item['ledger_status'] == 'Cleared' and item['outstanding'] == 0 for group in groups for item in group)
    with pytest.raises(ValueError, match='already cleared'):
        store.clear_reimbursements('Sid', kind, selected)


def test_reimbursement_clearance_rechecks_all_rows_before_writing(tmp_path):
    store = RequestStore(f'sqlite:///{tmp_path / "ledger.db"}')
    first, other_owner = trip(store), trip(store, creator='Nitish')
    selected = {number: store.get(number)['updated_at'] for number in (first, other_owner)}
    with pytest.raises(ValueError, match='one payer'):
        store.clear_reimbursements('Sid', 'upi', selected)
    assert store.reimbursement_clearings('Sid', 'upi') == {}
    with pytest.raises(ValueError, match='changed'):
        store.clear_reimbursements('Sid', 'upi', {first: 'stale version'})
    assert store.reimbursement_clearings('Sid', 'upi') == {}
    store.update(first, {'is_archived': True})
    with pytest.raises(ValueError, match='changed'):
        store.clear_reimbursements('Sid', 'upi', {first: store.get(first)['updated_at']})
    assert store.reimbursement_clearings('Sid', 'upi') == {}


@pytest.mark.parametrize('kind', ['upi', 'billtee'])
def test_reimbursement_tabs_render_cards_without_errors(kind):
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
import datetime as dt
import streamlit as st
from src.pending_payments import render_pending_payments
class Store:
    def pending_upi_profiles(self, user): return {}
    def list_upi_payments(self): return {}
    def list_billtee_payments(self): return {}
    def reimbursement_clearings(self, user, kind): return {}
trips = [{'request_number':'REQ-1', 'created_by':'Manish', 'report_scope':'Both',
          'trip_date':dt.date(2026,11,20), 'updated_at':'version',
          'vehicle_number':'MH01TEST', 'branch':'Wada', 'upi':500,
          'dtr_data':{'Billtee':300, 'Veh Placed by':'Manish'}}]
render_pending_payments('Sid', trips, {}, {}, Store())
''').run()
    app.session_state['pending_kind_card'] = kind
    app.run()
    assert not app.exception
    assert any(button.label == 'Update in Ledger' for button in app.button)
