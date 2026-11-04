import json
import pytest
from tests.test_pending_payments import trip
from src.records_store_v24 import RequestStore
from src.pending_payments import payment_groups
from src.billtee_payments import billtee_rtgs_rows


def test_billtee_independent_idempotent_and_rtgs_status(tmp_path):
    store = RequestStore(f'sqlite:///{tmp_path / "billtee.db"}')
    number = trip(store, dtr_data={'Billtee':100})
    before = store.get(number)
    selection = {number:before['updated_at']}
    assert store.send_pending_payments(selection, 'billtee', 'Sid') == 1
    assert store.send_pending_payments(selection, 'billtee', 'Sid') == 0
    assert store.get(number) == before
    assert not store.list_balance_payments() and not store.list_upi_payments()
    queued = store.list_billtee_payments()
    payload = json.loads(queued[number]['rtgs_data'])
    assert payload['BENE_ACC_NO'] == '001234' and payload['AMOUNT'] == 100
    rows = billtee_rtgs_rows([before], queued)
    assert rows[0]['request_number'] == 'BILLTEE:' + number
    assert rows[0]['_billtee_payment'] and not rows[0].get('_balance_payment')
    assert store.mark_rtgs_done([rows[0]['request_number']]) == 1
    assert store.list_billtee_payments()[number]['rtgs_done']
    store.mark_rtgs_done([rows[0]['request_number']], False)
    assert not store.list_billtee_payments()[number]['rtgs_done']
    assert store.send_pending_payments(selection, 'balance', 'Sid') == 1
    assert store.get(number) == before


def test_billtee_atomic_revalidation_and_permissions(tmp_path):
    store = RequestStore(f'sqlite:///{tmp_path / "validation.db"}')
    first = trip(store, dtr_data={'Billtee':100})
    second = trip(store, dtr_data={'Billtee':200}, rtgs_data={})
    selected = {number:store.get(number)['updated_at'] for number in (first,second)}
    with pytest.raises(ValueError, match='bank details'):
        store.send_pending_payments(selected, 'billtee', 'Sid')
    assert not store.list_billtee_payments()
    with pytest.raises(ValueError):
        store.send_pending_payments({first:selected[first]}, 'billtee', 'Nitish')
    with pytest.raises(ValueError, match='changed'):
        store.send_pending_payments({first:'stale'}, 'billtee', 'Sid')
    zero = trip(store, dtr_data={'Billtee':0})
    with pytest.raises(ValueError, match='positive'):
        store.send_pending_payments({zero:store.get(zero)['updated_at']}, 'billtee', 'Sid')


def test_billtee_transporter_grouping_positive_trips_only():
    trips = [{'request_number':str(i), 'transporter_name':name, 'ownership_type':'Own',
              'dtr_data':{'Billtee':value}, 'created_by':owner} for i,(name,value,owner) in enumerate([
        ('Vikash Roadlines',100,'Ajit'), ('Vikas Road lines',200,'Nitish'), ('Other',0,'Sid')])]
    groups = payment_groups(trips, 'billtee', {'0':{'rtgs_done':True}}, {})
    assert len(groups) == 1 and len(groups[0]) == 2
    assert sum(item['amount'] for item in groups[0]) == 300
    assert {item['status'] for item in groups[0]} == {'Pending','RTGS Done'}


def test_billtee_export_keeps_separate_trip_payment_identities():
    from src.rtgs_report import normalize_rtgs_records
    records = [{'BNF_NAME':'Test', 'BENE_ACC_NO':'001234', 'BENE_IFSC':'TEST0000001',
                'AMOUNT':100, 'REMARK':f'1234 Pune to Wada 0{day} 11 2026 Billtee Payment',
                '_payment_kind':'billtee', '_payment_id':f'BILLTEE:REQ-{day}'} for day in (1,2)]
    exported = normalize_rtgs_records(records)
    assert len(exported) == 2
    assert {row['_payment_id'] for row in exported} == {'BILLTEE:REQ-1','BILLTEE:REQ-2'}
