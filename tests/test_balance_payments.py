import datetime as dt
import json

import pandas as pd
import pytest
import xlrd

from src.balance_payments import BALANCE_PREFIX, balance_rtgs_rows, can_send_balance
from src.records_store_v12 import RequestStore
from src.rtgs_report import export_rtgs, normalize_rtgs_records


def test_balance_payment_lifecycle(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'balance.db'}")
    store.create({
        "trip_date": dt.date(2026, 10, 1), "report_scope": "DTR",
        "branch": "Pune", "created_by": "Nitish", "status": "Verified",
        "balance_amount": 2500, "rtgs_advance": 1000, "vehicle_number": "MH1234",
        "rtgs_data": {"BNF_NAME": "Demo", "BENE_ACC_NO": "00123", "BENE_IFSC": "ICIC0001234"},
    })
    original = store.list()[0]
    number = original["request_number"]
    with pytest.raises(ValueError):
        store.send_balance_payment(number, "Vijay")
    assert store.send_balance_payment(number, "Nitish")
    assert not store.send_balance_payment(number, "Nitish")
    assert store.list() == [original]
    payment = store.list_balance_payments()[number]
    assert float(payment["amount"]) == 2500
    assert json.loads(payment["rtgs_data"])["BENE_ACC_NO"] == "00123"
    assert store.mark_rtgs_done([BALANCE_PREFIX + number]) == 1
    assert store.list_balance_payments()[number]["rtgs_done"]
    assert not store.list()[0]["rtgs_done"]
    data = json.loads(payment["rtgs_data"])
    data["AMOUNT"] = 2400
    store.update_balance_payment(BALANCE_PREFIX + number, data, "Nikhat")
    assert store.list()[0]["balance_amount"] == original["balance_amount"]
    assert store.mark_rtgs_done([number, BALANCE_PREFIX + number]) == 2


@pytest.mark.parametrize("user", ["Ashok", "Ajit", "Nitish", "Sid", "Vinod", "Nikhil"])
def test_balance_permissions(user):
    row = {"branch": "Vadodara" if user == "Ashok" else "Pune", "report_scope": "DTR"}
    assert can_send_balance(user, row)
    assert not can_send_balance(user, {**row, "report_scope": "Expense"})
    assert not can_send_balance(user, {**row, "is_archived": True})


def test_balance_export_remains_separate_even_after_remark_edit():
    advance = {"BNF_NAME": "Demo", "BENE_ACC_NO": "00123", "BENE_IFSC": "ICIC0001234",
               "REMARK": "1234 Pune 01 10 2026 TA", "AMOUNT": 1000}
    balance = {**advance, "AMOUNT": 2500, "_payment_kind": "balance", "_payment_id": "BALANCE:1"}
    normalized = normalize_rtgs_records([advance, balance])
    assert len(normalized) == 2
    assert normalized[1]["_payment_kind"] == "balance"
    book = xlrd.open_workbook(file_contents=export_rtgs(pd.DataFrame(normalized)))
    sheet = book.sheet_by_index(0)
    assert sheet.nrows == 3
    assert [sheet.cell_value(i, 6) for i in (1, 2)] == [1000, 2500]


@pytest.mark.parametrize("amount", [0, -10])
def test_nonpositive_balance_not_queued(tmp_path, amount):
    store = RequestStore(f"sqlite:///{tmp_path / 'empty.db'}")
    number = store.create({"trip_date": dt.date.today(), "vehicle_number": "MH1234", "balance_amount": amount})
    with pytest.raises(ValueError):
        store.send_balance_payment(number, "Sid")
    assert store.list_balance_payments() == {}


def test_balance_rtgs_rows_ignore_trip_dates_and_use_request_dates_newest_first():
    trips = [
        {"request_number": "OLD", "trip_date": dt.date(2026, 7, 1), "beneficiary_name": "Old"},
        {"request_number": "NEW", "trip_date": dt.date(2026, 9, 1), "beneficiary_name": "New"},
    ]
    payments = {
        "OLD": {"request_number": "OLD", "amount": 900, "rtgs_done": False,
                "rtgs_data": '{"BNF_NAME": "Old balance"}', "created_at": dt.datetime(2026, 10, 3, 10)},
        "NEW": {"request_number": "NEW", "amount": 800, "rtgs_done": True,
                "rtgs_data": '{"BNF_NAME": "New balance"}', "created_at": dt.datetime(2026, 10, 2, 10)},
        "ARCHIVED": {"request_number": "ARCHIVED", "amount": 700, "rtgs_done": False,
                     "rtgs_data": '{}', "created_at": dt.datetime(2026, 10, 4, 10)},
    }
    rows = balance_rtgs_rows(trips, payments)
    assert [row["request_number"] for row in rows] == ["BALANCE:OLD", "BALANCE:NEW"]
    assert [row["trip_date"] for row in rows] == [dt.date(2026, 10, 3), dt.date(2026, 10, 2)]
    assert rows[1]["rtgs_done"] is True
