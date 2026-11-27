import datetime as dt

import pytest

from src.request_store import RequestStore


def test_archive_creator_trips_is_scoped_atomic_and_recoverable(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'archive.db'}")
    base = {'report_scope': 'Both', 'vehicle_number': 'TEST1234'}
    targets = [store.create({**base, 'created_by': 'Vijay', 'trip_date': dt.date(2026, 10, day)})
               for day in (10, 11)]
    other = store.create({**base, 'created_by': 'Nitish', 'trip_date': dt.date(2026, 10, 12)})
    outside = store.create({**base, 'created_by': 'Vijay', 'trip_date': dt.date(2026, 11, 1)})
    start, end = dt.date(2026, 10, 1), dt.date(2026, 10, 31)
    with pytest.raises(ValueError, match='No records were changed'):
        store.archive_creator_trips('Vijay', start, end, 3, 'Sid')
    assert all(not store.get(n)['is_archived'] for n in targets)
    assert store.archive_creator_trips('Vijay', start, end, 2, 'Sid') == 2
    assert all(store.get(n)['is_archived'] and store.get(n)['status'] == 'Cancelled' for n in targets)
    assert all(n not in {r['request_number'] for r in store.list()} for n in targets)
    assert not store.get(other)['is_archived'] and not store.get(outside)['is_archived']
    assert all(n in {r['request_number'] for r in store.list(include_archived=True)} for n in targets)
