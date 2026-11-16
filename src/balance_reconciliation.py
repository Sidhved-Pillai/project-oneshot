"""Pending-only confirmed balances. Source trips and financial reports stay intact."""
import datetime as dt
import json
from decimal import Decimal

PREFIX = 'BALREC-'


def unpack(value):
    return value if isinstance(value, dict) else json.loads(value or '{}')


def money(value):
    return Decimal(str(value or 0)).quantize(Decimal('.01'))


def day(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def name_key(value):
    from .pending_payments import transporter_key
    return transporter_key(value)


def reconciliation_row(record, value=None):
    snapshot = unpack(record['snapshot'])
    return {**snapshot.get('profile_row', {}), 'request_number': record['request_number'],
            'trip_date': day(record['cutoff']), 'updated_at': record['updated_at'],
            'transporter_name': record['transporter_name'], 'report_scope': 'Both',
            'ownership_type': 'Outside', 'balance_amount': float(money(record['amount']) if value is None else value),
            'revenue': 0, 'transporter_freight': 0, 'total_advance': 0, 'upi': 0,
            'is_archived': False, 'status': 'Verified',
            'notes': f"Confirmed outstanding balance as at {day(record['cutoff']):%d/%m/%Y}; supplied by Sid. Not an individual trip.",
            'dtr_data': {}, '_confirmed_balance': True}


def balance_view(trips, payments, reconciliations):
    """Replace covered history with an opening balance, retaining later/new trips.

    A credit offsets later pending balances. No historical trip is labelled paid,
    deleted or altered. Previously queued amounts continue to use their saved value.
    """
    rows = {r['request_number']: dict(r) for r in trips}
    credits = []
    for record in reconciliations:
        snapshot = unpack(record['snapshot'])
        covered = set(snapshot['covered_records'])
        aliases = {name_key(n) for n in snapshot['aliases']}
        cutoff = day(record['cutoff'])
        for number, row in list(rows.items()):
            if row.get('report_scope') != 'Expense' and name_key(row.get('transporter_name') or unpack(row.get('dtr_data')).get('Transporter Name')) in aliases:
                rows[number] = {**row, '_pending_transporter_name': record['transporter_name']}
        # Payments requested after the closing-balance date reduce the carry-forward.
        later_paid = sum((money(p['amount']) for number,p in payments.items()
                          if number in covered and day(p['created_at']) > cutoff), Decimal(0))
        opening = money(record['amount']) - later_paid
        for number in covered:
            rows.pop(number, None)
        if opening > 0:
            rows[record['request_number']] = reconciliation_row(record, opening)
        elif opening < 0:
            credit = -opening
            candidates = [r for r in rows.values() if r['request_number'] not in covered
                          and not r.get('_confirmed_balance') and r.get('report_scope') != 'Expense'
                          and not r.get('is_archived') and r.get('status') != 'Cancelled'
                          and not str(r.get('ownership_type') or '').lower().startswith('own')
                          and name_key(r.get('transporter_name') or unpack(r.get('dtr_data')).get('Transporter Name')) in aliases]
            # Credit already applied by this workflow remains consumed on reload.
            used = sum((money(unpack(payment.get('rtgs_data')).get('_balance_credit_applied'))
                        for payment in payments.values()
                        if unpack(payment.get('rtgs_data')).get('_balance_reconciliation_id') == record['request_number']), Decimal(0))
            credit = max(Decimal(0),credit-used)
            for row in sorted(candidates,key=lambda r:(str(r.get('trip_date')),r['request_number'])):
                if row['request_number'] in payments:
                    continue
                original = max(Decimal(0),money(row.get('balance_amount')))
                applied = min(credit,original)
                credit -= applied
                rows[row['request_number']] = {**row,'balance_amount':float(original-applied),
                                               '_balance_credit_applied':float(applied), '_balance_reconciliation_id':record['request_number']}
            if credit:
                credits.append({'name':record['transporter_name'],'amount':float(credit),'cutoff':cutoff})
    return list(rows.values()), credits
