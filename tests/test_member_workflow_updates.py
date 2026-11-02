import datetime as dt

import pytest
from src.diesel_inputs import update_diesel
from src.expense_date import seed_expense_date, remember_expense_date
from src.entry_state import clear_expense_state
from src.pending_payments import payment_groups
from src.payment_access import PENDING_PAYMENT_USERS
from src.records_store_v21 import RequestStore
from tests.test_pending_payments import trip
from tests.test_batched_interactions import trip_app


@pytest.mark.parametrize('pair,expected', [
    ({'diesel_quantity':20,'diesel_rate':90}, {'diesel_advance':1800}),
    ({'diesel_quantity':20,'diesel_advance':1800}, {'diesel_rate':90}),
    ({'diesel_rate':90,'diesel_advance':1800}, {'diesel_quantity':20}),
])
def test_any_two_diesel_inputs_solve_third(pair, expected):
    state = {}
    for field,value in pair.items():
        state['trip_'+field] = value
        update_diesel(state,'trip',field)
    for field,value in expected.items():
        assert state['trip_'+field] == value


def test_diesel_amount_is_editable_and_can_derive_rate_in_ui():
    app = trip_app('Vijay')
    next(w for w in app.number_input if w.label == 'Diesel Qty (L)').set_value(20).run()
    next(w for w in app.number_input if w.label == 'Diesel (₹)').set_value(1800).run()
    assert not app.exception
    assert app.session_state['test_returned_values']['diesel_rate'] == 90
    next(w for w in app.number_input if w.label == 'Diesel Rate (₹/L)').set_value(100).run()
    assert not app.exception
    # Amount and rate are now the two most recently entered values.
    assert app.session_state['test_returned_values']['diesel_quantity'] == 18


def test_fuzzy_transporter_groups_preserve_per_trip_accounts():
    rows = [{'request_number':str(i),'transporter_name':name, 'balance_amount':100,
             'rtgs_data':{'BNF_NAME':'Example','BENE_ACC_NO':account,'BENE_IFSC':'TEST0000001'}}
            for i,(name,account) in enumerate([
                ('VIKASH ROADLINES',''), ('Vikash Road lines','001'), ('Vikas Roadlines','002'),
                ('BHARDWAJ ROADLINES',''), ('Bhardwaj Roadlines','003')])]
    groups = payment_groups(rows,'balance',{}, {})
    assert sorted(map(len,groups)) == [2,3]
    assert {item['profile']['BENE_ACC_NO'] for group in groups for item in group} == {'','001','002','003'}


def test_nikhat_expense_date_survives_form_clear_without_affecting_others():
    state = {'expense_0_date':dt.date(2026,10,15)}
    remember_expense_date(state,'Nikhat',state['expense_0_date'])
    clear_expense_state(state)
    seed_expense_date(state,'Nikhat','expense_1')
    assert state['expense_1_date'] == dt.date(2026,10,15)
    state['expense_1_date'] = dt.date(2026,10,16)
    seed_expense_date(state,'Nikhat','expense_1')
    assert state['expense_1_date'] == dt.date(2026,10,16)
    seed_expense_date(state,'Vijay','expense_2')
    assert 'expense_2_date' not in state


def test_only_approved_reviewers_can_access_and_send_pending_payments(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path/'access.db'}")
    assert PENDING_PAYMENT_USERS == {'Vinod','Nikhil','Sid','Ajit','Shyam'}
    for user in PENDING_PAYMENT_USERS:
        number = trip(store)
        assert store.send_pending_payments({number:store.get(number)['updated_at']},'balance',user) == 1
    for user in ('Nikhat','Vijay','Manish','Nitish','Ashok'):
        with pytest.raises(ValueError,match='access'):
            store.pending_upi_profiles(user)
        with pytest.raises(ValueError,match='access'):
            store.send_pending_payments({},'balance',user)
