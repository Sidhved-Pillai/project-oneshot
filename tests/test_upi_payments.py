import datetime as dt
import json

import pytest

from src.records_store_v13 import RequestStore
from src.upi_payments import can_send_upi, upi_rtgs_rows, UPI_PREFIX
from src.balance_payments import BALANCE_PREFIX
from src.rtgs_report_v2 import normalize_rtgs_records


def test_upi_export_does_not_merge_separate_trip_requests():
    base = {'BNF_NAME': 'Transporter', 'BENE_ACC_NO': '001234', 'BENE_IFSC': 'BANK0001234',
            'AMOUNT': 1250, 'REMARK': '1234 Pune to Mumbai 01 09 2026 UPI Payment', '_payment_kind': 'upi'}
    output = normalize_rtgs_records([{**base, '_payment_id': 'UPI:A'}, {**base, '_payment_id': 'UPI:B'}])
    assert len(output) == 2
    assert {row['_payment_id'] for row in output} == {'UPI:A', 'UPI:B'}


def trip(store, **extra):
    return store.create({'created_by': 'Nitish', 'branch': 'Pune', 'report_scope': 'Both',
        'trip_date': dt.date(2026,9,1), 'vehicle_number': 'MH12AB1234', 'upi': 1250,
        'rtgs_advance': 5000, 'balance_amount': 2000, 'beneficiary_name': 'Transporter',
        'rtgs_data': {'BENE_ACC_NO': '001234', 'BENE_IFSC': 'BANK0001234', 'AMOUNT': 5000},
        **extra})


def test_upi_request_is_explicit_unique_and_independent(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'payments.db'}")
    number = trip(store)
    before = store.get(number)
    assert store.list_upi_payments() == {}
    assert store.send_upi_payment(number, 'Nitish')
    assert not store.send_upi_payment(number, 'Nitish')
    assert store.send_balance_payment(number, 'Nitish')
    assert store.get(number) == before
    payment = store.list_upi_payments()[number]
    raw = json.loads(payment['rtgs_data'])
    assert raw['AMOUNT'] == 1250 and raw['BENE_ACC_NO'] == '001234'
    assert raw['_payment_kind'] == 'upi'
    rows = upi_rtgs_rows(store.list(), store.list_upi_payments())
    assert len(rows) == 1 and rows[0]['request_number'] == UPI_PREFIX + number
    assert rows[0]['trip_date'] != before['trip_date']
    assert rows[0]['_upi_payment'] and not rows[0].get('_balance_payment')
    assert store.mark_rtgs_done([UPI_PREFIX + number]) == 1
    assert store.list_upi_payments()[number]['rtgs_done']
    assert not store.get(number)['rtgs_done']
    assert not store.list_balance_payments()[number]['rtgs_done']
    assert store.mark_rtgs_done([UPI_PREFIX + number, BALANCE_PREFIX + number, number], False) == 3
    store.update_upi_payment(UPI_PREFIX + number, {**raw, 'AMOUNT': 1300}, 'Nikhat')
    assert store.list_upi_payments()[number]['amount'] == 1300
    assert store.get(number)['upi'] == 1250


@pytest.mark.parametrize('extra', [{'upi': 0}, {'created_by': 'Ajit'}, {'branch': 'Wada'},
    {'status': 'Cancelled'}, {'is_archived': True}, {'report_scope': 'Expense'}])
def test_ineligible_trips_cannot_queue_upi(tmp_path, extra):
    store = RequestStore(f"sqlite:///{tmp_path / 'payments.db'}")
    number = trip(store, **extra)
    assert not can_send_upi('Nitish', store.get(number))
    with pytest.raises(ValueError):
        store.send_upi_payment(number, 'Nitish')


def test_other_users_cannot_queue_nitish_upi(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'payments.db'}")
    number = trip(store)
    with pytest.raises(ValueError):
        store.send_upi_payment(number, 'Sid')
