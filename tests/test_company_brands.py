import datetime as dt
import json
import pytest
from src.text_normalization import canonical_company
from src.company_brands import company_brand_update
from src.request_store import RequestStore


@pytest.mark.parametrize('value,expected', [
    ('Saint-Gobain India Private Limited - Gyproc', 'Saint Gobain - Gyproc'),
    ('saint gobain weber business', 'Saint Gobain - Weber'),
    ('Gyprok', 'Saint Gobain - Gyproc'),
    ('Gyporc', 'Saint Gobain - Gyproc'),
    ('Webber', 'Saint Gobain - Weber'),
    ('saint gobian waber', 'Saint Gobain - Weber'),
    ('SG - Weber', 'Saint Gobain - Weber'),
])
def test_business_names_and_typoes(value, expected):
    assert canonical_company(value) == expected
    assert canonical_company(expected, ['Saint-Gobain India Private Limited']) == expected


def test_generic_company_is_not_guessed_and_conflicting_brands_not_migrated():
    assert canonical_company('Saint Gobain') == 'Saint-Gobain India Private Limited'
    assert canonical_company('Weber Transport') == 'Weber Transport'
    assert company_brand_update({'company_name':'Saint Gobain','dtr_data':{}}) is None
    assert company_brand_update({'company_name':'Saint Gobain - Weber','dtr_data':{'Compnay Name':'Saint Gobain - Gyproc'}}) is None


def test_legacy_repair_updates_record_and_dtr_without_changing_trip_values(tmp_path):
    store = RequestStore(f'sqlite:///{tmp_path / "brands.db"}')
    number = store.create({'created_by':'Ashok','trip_date':dt.date(2026,9,1),'vehicle_number':'TEST1234',
        'company_name':'Saint-Gobain India Private Limited - Gyproc','revenue':9000,
        'dtr_data':{'Compnay Name':'Saint-Gobain India Private Limited - Gyproc','Invoice No.':'1, 2','LR No.':'LR123'},
        'source_image':b'original evidence'})
    before = store.get(number)
    evidence = store.get_evidence(number)
    assert store.repair_company_brands()['updated'] == [number]
    after = store.get(number)
    assert after['company_name'] == 'Saint Gobain - Gyproc'
    raw = json.loads(after['dtr_data'])
    assert raw['Compnay Name'] == 'Saint Gobain - Gyproc'
    assert raw['Invoice No.'] == '1, 2' and raw['LR No.'] == 'LR123'
    for field in ('revenue','trip_date','created_by','vehicle_number'):
        assert after[field] == before[field]
    assert store.get_evidence(number) == evidence
    from sqlalchemy import select
    from src.request_store import record_revisions
    with store.engine.connect() as conn:
        snapshots = conn.execute(select(record_revisions.c.snapshot).where(
            record_revisions.c.request_number == number,
            record_revisions.c.change_source == 'before_company_business_normalization',
        )).scalars().all()
    assert len(snapshots) == 1
    assert json.loads(snapshots[0])['company_name'] == before['company_name']
    assert store.repair_company_brands()['updated'] == []
