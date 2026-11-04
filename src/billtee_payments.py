"""Separate Billtee RTGS identities; never alter balance or advance payments."""
from .balance_payments import balance_rtgs_rows, BALANCE_PREFIX


def billtee_rtgs_rows(trips, payments):
    rows = balance_rtgs_rows(trips, payments)
    for row in rows:
        row['request_number'] = 'BILLTEE:' + row['request_number'].removeprefix(BALANCE_PREFIX)
        row.pop('_balance_payment', None)
        row['_billtee_payment'] = True
    return rows
