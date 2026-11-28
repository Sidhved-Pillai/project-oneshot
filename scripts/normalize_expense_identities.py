"""Normalize the confirmed expense identity typos with request audit revisions.

Set DATABASE_URL and pass --apply after reviewing the dry-run counts.
"""
import argparse
import json
import os
from collections import Counter

from sqlalchemy import create_engine, select, or_

from src.request_store import RequestStore, requests


BENEFICIARIES = {
    'National Tyre': 'National Tyres',
    'Nitish Kumar Jha': 'Nitish Jha',
    'Hirdyanand': 'Hirdayanand',
    'Hridyanand': 'Hirdayanand',
}
DRIVERS = {'Hridyanand': 'Hirdayanand', 'Hirdyanand': 'Hirdayanand'}
VEHICLES = {'MH0HLE8408': 'MH04LE8408'}


def changes_for(row):
    changes = {}
    beneficiary = str(row.get('beneficiary_name') or '').strip()
    if beneficiary in BENEFICIARIES:
        changes['beneficiary_name'] = BENEFICIARIES[beneficiary]
    vehicle = str(row.get('vehicle_number') or '').strip()
    if vehicle in VEHICLES:
        changes['vehicle_number'] = VEHICLES[vehicle]

    rtgs = json.loads(row.get('rtgs_data') or '{}')
    if changes.get('beneficiary_name') and str(rtgs.get('BNF_NAME') or '').strip() == beneficiary:
        changes['rtgs_data'] = {**rtgs, 'BNF_NAME': changes['beneficiary_name']}
    dtr = json.loads(row.get('dtr_data') or '{}')
    dtr_changed = False
    driver = str(dtr.get('Driver Name') or '').strip()
    if driver.casefold() in {name.casefold() for name in DRIVERS}:
        dtr['Driver Name'] = 'Hirdayanand'
        dtr_changed = True
    if changes.get('vehicle_number') and str(dtr.get('Vehicle No.') or '').strip() == vehicle:
        dtr['Vehicle No.'] = changes['vehicle_number']
        dtr_changed = True
    if dtr_changed:
        changes['dtr_data'] = dtr
    return changes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    url = os.environ.get('DATABASE_URL')
    if not url:
        parser.error('DATABASE_URL is required')
    store = RequestStore.__new__(RequestStore)
    url = url.replace('postgres://', 'postgresql+psycopg://').replace('postgresql://', 'postgresql+psycopg://')
    store.engine = create_engine(url,
                                 connect_args={'prepare_threshold': None})
    with store.engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(select(
            requests.c.request_number, requests.c.updated_at, requests.c.beneficiary_name,
            requests.c.vehicle_number, requests.c.rtgs_data, requests.c.dtr_data,
        ).where(
            requests.c.is_archived.is_(False), requests.c.status != 'Cancelled',
            or_(requests.c.beneficiary_name.in_(tuple(BENEFICIARIES) + ('Hridyanand ',)),
                requests.c.vehicle_number.in_(VEHICLES),
                requests.c.dtr_data.ilike('%ridyanand%'),
                requests.c.dtr_data.ilike('%irdyanand%')),
        )).mappings()]
    changes = [(row['request_number'], values) for row in rows if (values := changes_for(row))]
    counts = Counter(field for _, values in changes for field in values)
    print(f'{len(changes)} records affected: {dict(counts)}')
    if args.apply and changes:
        updated = store.update_many(changes, 'identity_normalization_20261128', 'Sid',
                                    {row['request_number']: row['updated_at'] for row in rows})
        print(f'{updated} records updated with before/after audit revisions')


if __name__ == '__main__':
    main()
