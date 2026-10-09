"""Audited September reconciliation. Dry-run by default; credentials from environment."""
import datetime as dt
import json
import os
import re
import sys

import pandas as pd
from sqlalchemy import create_engine, select, update

from src.request_store import requests, REQUEST_METADATA_COLUMNS, RequestStore, engine_options

# Individually reviewed workbook LR -> existing request for transcription differences.
REVIEWED = dict(zip(
    [32677,32686,32701,32703,32720,32742,32743,32745,32750,32751,32752,32759,32770,32775,32780,32782,32790,32792,32798,32810],
    [1073,1080,1091,1093,1112,1136,1135,1132,1142,1141,1144,1247,1258,1534,1737,1546,1745,1747,1753,1765],
))

def normalized(value):
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())

def recovered_date(row):
    date = row['trip_date']
    return dt.date(2026, 9, date.month) if date.day == 9 and date.month != 9 else date

def plan(rows, frame):
    active = [r for r in rows if not r['is_archived'] and r['status'] != 'Cancelled']
    september = [r for r in active if not r['request_number'].startswith('REQ-202610')]
    used = set()
    changes = []
    for _, x in frame.iterrows():
        date = pd.to_datetime(x['DATE'], dayfirst=True).date()
        lr = int(x['LR NO '])
        if lr in REVIEWED:
            candidates = [r for r in september if r['id'] == REVIEWED[lr]]
        else:
            candidates = [r for r in september if recovered_date(r) == date and
                          normalized(r['vehicle_number']) == normalized(x['VEHICEL NO.'])]
        if len(candidates) != 1 or candidates[0]['request_number'] in used:
            raise ValueError(f'Unresolved workbook LR {lr}: {len(candidates)} candidates')
        row = candidates[0]
        used.add(row['request_number'])
        dtr = json.loads(row['dtr_data'] or '{}')
        vehicle = normalized(x['VEHICEL NO.'])
        revenue, freight = float(x['Booking/Freight']), float(x['Transporter Freight'])
        advance = float(x['Advance']) if pd.notna(x['Advance']) else 0
        diesel = float(x['Diesel']) if pd.notna(x['Diesel']) else 0
        total = float(x['Total Adv.']) if pd.notna(x['Total Adv.']) else 0
        cash_upi = float(row['cash_advance'] or 0) + float(row['upi'] or 0)
        if cash_upi > advance or abs(total - advance - diesel) > .01:
            raise ValueError(f'Unresolved payment allocation for LR {lr}')
        rtgs = json.loads(row['rtgs_data'] or '{}')
        rtgs['AMOUNT'] = advance - cash_upi
        dtr.update({'Date': str(date), 'Vehicle No.': vehicle, 'Revenue': revenue,
                    'Transporter Freight': freight, 'RTGS ADVANCE': advance - cash_upi,
                    'Diesel Adv.': diesel, 'Total Adv.': total, 'Balance Amt.': freight - total,
                    '_september_workbook_lr': lr})
        origin, destination = str(x['From']).strip().title(), str(x['To']).strip().title()
        capacity = str(x['Loaded Weight']).strip().upper().replace('MT', ' MT').strip()
        transporter = str(x['Vehicle (Own/Outside)']).strip()
        dtr.update({'From': origin, 'To': destination, 'Vehicle Type': capacity,
                    'Transporter Name': transporter})
        changes.append((row, {'trip_date': date, 'vehicle_number': vehicle,
                              'from_location': origin, 'to_location': destination,
                              'vehicle_type': capacity, 'transporter_name': transporter,
                              'revenue': revenue, 'transporter_freight': freight,
                              'rtgs_advance': advance - cash_upi, 'diesel_advance': diesel,
                              'total_advance': total, 'amount': total, 'balance_amount': freight - total,
                              'rtgs_data': rtgs, 'dtr_data': dtr}))
    if len(used) != 137:
        raise ValueError('Expected exactly 137 distinct workbook trips')
    extras = [r for r in september if r['request_number'] not in used]
    if any(r['request_number'] != 'REQ-202607-001211' for r in extras):
        raise ValueError('Unmatched existing September candidates: ' + str([(r['request_number'], str(r['trip_date'])) for r in extras]))
    for row in extras:
        # Keep the unmatched July invoice recoverable, outside active reports.
        changes.append((row, {'is_archived': True}))
    for row in active:
        if row['request_number'].startswith('REQ-202610') and row['trip_date'].month != 10:
            date = row['trip_date']
            if date.day != 10 or date.year != 2026:
                raise ValueError('Unresolved October date')
            date = dt.date(2026, 10, date.month)
            dtr = json.loads(row['dtr_data'] or '{}')
            dtr['Date'] = str(date)
            changes.append((row, {'trip_date': date, 'dtr_data': dtr}))
    return changes

def run(url, workbook, apply=False):
    url = url.replace('postgres://','postgresql+psycopg://',1).replace('postgresql://','postgresql+psycopg://',1)
    engine = create_engine(url, **engine_options(url))
    store = RequestStore.__new__(RequestStore)
    store.engine = engine
    frame = pd.read_excel(workbook).dropna(subset=['DATE'])
    with engine.begin() as conn:
        rows = [dict(r) for r in conn.execute(select(*REQUEST_METADATA_COLUMNS).where(
            requests.c.created_by == 'Ashok').with_for_update()).mappings()]
        changes = plan(rows, frame)
        print('Validated workbook trips:', len(frame), 'planned updates:', len(changes))
        if not apply:
            return
        for row, values in changes:
            store._insert_revision(conn, row['request_number'], row, 'before_september_workbook_reconciliation', 'Sid')
            conn.execute(update(requests).where(requests.c.id == row['id']).values(
                **store._clean_values(values), updated_at=dt.datetime.now()))
            after = dict(conn.execute(select(*REQUEST_METADATA_COLUMNS).where(requests.c.id == row['id'])).mappings().one())
            store._insert_revision(conn, row['request_number'], after, 'september_workbook_reconciliation', 'Sid')
        verified = [dict(r) for r in conn.execute(select(*REQUEST_METADATA_COLUMNS).where(
            requests.c.created_by == 'Ashok', requests.c.is_archived.is_(False), requests.c.status != 'Cancelled')).mappings()]
        september = [r for r in verified if r['trip_date'].month == 9 and r['trip_date'].year == 2026]
        assert len(september) == 137
        assert all(r['trip_date'].year == 2026 and r['trip_date'].month in (9,10) for r in verified)
        assert sum(float(r['revenue']) for r in september) == float(frame['Booking/Freight'].sum())
        assert sum(float(r['transporter_freight']) for r in september) == float(frame['Transporter Freight'].sum())
        assert sum(float(r['total_advance']) for r in september) == float(frame['Total Adv.'].sum())
        for row, values in changes:
            after = next(r for r in verified if r['id'] == row['id']) if not values.get('is_archived') else None
            if after:
                for key in ('source_filename', 'invoice_number', 'beneficiary_name', 'rtgs_done', 'batch_id'):
                    assert after[key] == row[key], f'Unexpected change: {key}'
                original_rtgs = json.loads(row['rtgs_data'] or '{}')
                new_rtgs = json.loads(after['rtgs_data'] or '{}')
                assert {k:v for k,v in original_rtgs.items() if k!='AMOUNT'} == {k:v for k,v in new_rtgs.items() if k!='AMOUNT'}
        print('Verified live September: 137; all active Ashok dates September/October 2026; revenue matches workbook.')

if __name__ == '__main__':
    run(os.environ['DATABASE_URL'], sys.argv[1], '--apply' in sys.argv)
