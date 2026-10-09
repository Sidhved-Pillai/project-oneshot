import datetime as dt
import pandas as pd
import pytest

from src.dtr_dates import parse_dtr_date, dtr_editor_key
from src.ashok_dates import parse_month_date


def test_month_helper_import_with_cached_previous_date_module():
    import subprocess
    import sys
    code = '''
import sys, types, datetime
old = types.ModuleType("src.dtr_dates")
old.parse_dtr_date = lambda value: datetime.date(2026, 9, 10)
sys.modules["src.dtr_dates"] = old
from src.ashok_dates import parse_month_date
assert parse_month_date("10/09/2026", datetime.date(2026,10,1)) == datetime.date(2026,10,9)
'''
    subprocess.run([sys.executable, '-c', code], check=True)


@pytest.mark.parametrize('value', ['09/10/2026', '10/09/2026', '2026-10-09', dt.date(2026,9,10)])
def test_ashok_current_month_resolves_both_date_orders(value):
    assert parse_month_date(value, dt.date(2026,10,9)) == dt.date(2026,10,9)


@pytest.mark.parametrize('value', ['2025-10-09', '2026-11-15', '2026-01-20', None, 'invalid'])
def test_outside_month_is_rejected_not_silently_replaced(value):
    assert parse_month_date(value, dt.date(2026,10,9)) is None


def test_historical_edit_keeps_historical_month():
    assert parse_month_date('09/02/2026', dt.date(2026,9,1)) == dt.date(2026,9,2)
    assert parse_month_date('2026-10-14', dt.date(2026,9,1)) is None
from src.records_store_v12 import RequestStore


@pytest.mark.parametrize("value", ["2026-09-01", "01/09/2026", "01.09.2026", dt.date(2026, 9, 1), "2026-09-01 00:00:00"])
def test_iso_and_indian_dates_keep_september(value):
    assert parse_dtr_date(value) == dt.date(2026, 9, 1)


@pytest.mark.parametrize("value", [None, pd.NaT, 2026, 45000, "2026", "not a date"])
def test_invalid_or_numeric_dates_cannot_turn_into_1970(value):
    assert parse_dtr_date(value) is None


def test_editor_identity_changes_with_rows_order_or_updates():
    rows = [{"request_number": "A", "updated_at": "1", "dtr_data": "{}"},
            {"request_number": "B", "updated_at": "1", "dtr_data": "{}"}]
    original = dtr_editor_key(rows, "start", "end")
    assert original == dtr_editor_key(list(rows), "start", "end")
    assert original != dtr_editor_key(list(reversed(rows)), "start", "end")
    assert original != dtr_editor_key(rows[:1], "start", "end")
    assert original != dtr_editor_key([{**rows[0], "updated_at": "2"}, rows[1]], "start", "end")


def test_stale_dtr_save_rolls_back_entire_batch(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'dtr.db'}")
    a = store.create({"created_by": "Ashok", "vehicle_number": "MH1234", "trip_date": dt.date(2026, 9, 1), "revenue": 100})
    b = store.create({"created_by": "Ashok", "vehicle_number": "MH5678", "trip_date": dt.date(2026, 9, 2), "revenue": 200})
    versions = {row["request_number"]: row.get("updated_at") for row in store.list()}
    store.update(b, {"revenue": 300})
    with pytest.raises(ValueError):
        store.update_many([(a, {"revenue": 999}), (b, {"revenue": 999})], expected_versions=versions)
    rows = {row["request_number"]: row for row in store.list()}
    assert rows[a]["revenue"] == 100
    assert rows[b]["revenue"] == 300
    latest = {number: row.get("updated_at") for number, row in rows.items()}
    assert store.update_many([(a, {"revenue": 150}), (b, {"revenue": 350})], expected_versions=latest) == 2
