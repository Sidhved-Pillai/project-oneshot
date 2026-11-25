import datetime as dt
import json

from sqlalchemy import select

from src.request_store import RequestStore, record_revisions, requests
from src.saint_gobain_grouping import group_legacy_trips


def test_grouping_prefers_dtr_then_matching_route():
    rows = [
        {'request_number': 'label', 'company_name': 'Saint Gobain - Weber',
         'from_location': 'Wada', 'to_location': 'Pune', 'branch': 'Wada', 'dtr_data': {}},
        {'request_number': 'route', 'company_name': 'Saint-Gobain India Private Limited',
         'from_location': 'Wada', 'to_location': 'Pune', 'branch': 'Wada',
         'dtr_data': {'Compnay Name': 'Saint-Gobain India Private Limited'}},
        {'request_number': 'dtr', 'company_name': 'Saint Gobain - Weber',
         'from_location': 'Talegaon', 'to_location': 'Mumbai', 'branch': 'Pune',
         'dtr_data': {'Compnay Name': 'Saint Gobain - Gyproc'}},
    ]
    groups = group_legacy_trips(rows)
    assert groups['route'][0] == 'Saint Gobain - Weber'
    assert groups['dtr'][0] == 'Saint Gobain - Gyproc'


def test_one_time_repair_preserves_every_dtr_and_trip(tmp_path):
    store = RequestStore(f'sqlite:///{tmp_path / "saint-gobain.db"}')
    common = {'trip_date': dt.date(2026, 11, 24), 'vehicle_number': 'MH04AB1234',
              'from_location': 'Wada', 'to_location': 'Pune', 'branch': 'Wada'}
    store.create({**common, 'company_name': 'Saint Gobain - Weber',
                  'dtr_data': {'Compnay Name': 'Saint Gobain - Weber'}})
    number = store.create({**common, 'company_name': 'Saint-Gobain India Private Limited',
                           'revenue': 9000, 'source_image': b'original invoice',
                           'dtr_data': {'Compnay Name': 'Saint-Gobain India Private Limited',
                                        'Invoice No.': '12345', 'LR No.': 'ABC'}})
    before = store.get(number)
    evidence = store.get_evidence(number)
    with store.engine.connect() as conn:
        count_before = conn.execute(select(requests.c.id)).all()
    result = store.repair_saint_gobain_groups()
    after = store.get(number)
    assert result == {'updated': 1, 'gyproc': 0, 'weber': 1}
    assert after['company_name'] == 'Saint Gobain - Weber'
    assert after['dtr_data'] == before['dtr_data']
    assert after['revenue'] == before['revenue']
    assert after['trip_date'] == before['trip_date']
    assert store.get_evidence(number) == evidence
    with store.engine.connect() as conn:
        assert conn.execute(select(requests.c.id)).all() == count_before
        revisions = conn.execute(select(record_revisions.c.snapshot).where(
            record_revisions.c.request_number == number,
            record_revisions.c.change_source.in_(['before_sg_group_repair', 'sg_group_repair']),
        ).order_by(record_revisions.c.id)).scalars().all()
    assert len(revisions) == 2
    assert json.loads(revisions[0])['company_name'] == before['company_name']
    assert json.loads(revisions[1])['company_name'] == after['company_name']
    assert all(json.loads(snapshot)['dtr_data'] == before['dtr_data'] for snapshot in revisions)
    assert store.repair_saint_gobain_groups()['updated'] == 0
