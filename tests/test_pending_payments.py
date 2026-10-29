import datetime as dt
import json

import pytest
from sqlalchemy import insert
from src.pending_payments import payment_groups
from src.records_store_v20 import RequestStore
from src.request_store import upi_reimbursement_profiles


def trip(store, **extra):
    return store.create({'created_by':'Nitish', 'report_scope':'Both', 'trip_date':dt.date(2026,10,29),
        'vehicle_number':'TEST1234', 'transporter_name':'Sai Transporter', 'branch':'Pune',
        'ownership_type':'Outside', 'balance_amount':2000, 'upi':500, 'beneficiary_name':'Test Transporter',
        'rtgs_data':{'BNF_NAME':'Test Transporter','BENE_ACC_NO':'001234','BENE_IFSC':'TEST0000001'}, **extra})


def test_grouped_balance_sends_selected_once_and_preserves_trips(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'pending.db'}")
    numbers = [trip(store), trip(store)]
    before = {number:store.get(number) for number in numbers}
    groups = payment_groups(list(before.values()), 'balance', {}, {})
    assert len(groups) == 1 and len(groups[0]) == 2
    selected = {number:row['updated_at'] for number,row in before.items()}
    with pytest.raises(ValueError):
        store.send_pending_payments(selected, 'balance', 'Shyam')
    assert store.send_pending_payments(selected, 'balance', 'Sid') == 2
    assert store.send_pending_payments(selected, 'balance', 'Sid') == 0
    assert store.list_balance_payments().keys() == before.keys()
    assert {number:store.get(number) for number in numbers} == before


def test_upi_uses_payers_profile_and_missing_profile_rolls_back_batch(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'upi.db'}")
    numbers = [trip(store), trip(store, created_by='Gopal')]
    with store.engine.begin() as conn:
        conn.execute(insert(upi_reimbursement_profiles).values(user_name='Nitish', beneficiary_data=json.dumps({
            'BNF_NAME':'Test Payer', 'BENE_ACC_NO':'009876', 'BENE_IFSC':'TEST0000002'})))
    selected = {number:store.get(number)['updated_at'] for number in numbers}
    with pytest.raises(ValueError, match='not configured'):
        store.send_pending_payments(selected, 'upi', 'Sid')
    assert store.list_upi_payments() == {}
    assert store.send_pending_payments({numbers[0]:selected[numbers[0]]}, 'upi', 'Sid') == 1
    queued = json.loads(store.list_upi_payments()[numbers[0]]['rtgs_data'])
    assert queued['BNF_NAME'] == 'Test Payer'
    assert queued['BENE_ACC_NO'] == '009876'
    assert queued['AMOUNT'] == 500


def test_stale_trip_rejected_and_own_profit_excluded(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'stale.db'}")
    number = trip(store)
    with pytest.raises(ValueError, match='changed'):
        store.send_pending_payments({number:'old-version'}, 'balance', 'Sid')
    assert not store.list_balance_payments()
    row = store.get(number)
    assert not payment_groups([{**row, 'ownership_type':'Own'}], 'balance', {}, {})
    other_bank = {**row, 'rtgs_data':{'BNF_NAME':'Other','BENE_ACC_NO':'other','BENE_IFSC':'TEST0000001'}}
    assert len(payment_groups([row,other_bank], 'balance', {}, {})) == 2
