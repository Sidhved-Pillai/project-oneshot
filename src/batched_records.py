"""Filter controls submitted as one request rather than per-field reruns."""
import datetime as dt
import json

import streamlit as st

from .record_filters_v2 import RECORD_TYPES, TRIP_RECORDS, DIRECT_EXPENSES, direct_expense_headings
from .vehicle_normalization import canonical_vehicle_number
from .vehicle_placer import canonical_vehicle_placer
from .number_format import format_inr
from .operational_dates_v2 import OPERATIONS_START


def render_filters(rows, user, today):
    def data(row):
        raw = row.get('dtr_data') or {}
        return json.loads(raw) if isinstance(raw, str) else raw
    vehicles = sorted({canonical_vehicle_number(r.get('vehicle_number')) for r in rows} - {''})
    placers = sorted({canonical_vehicle_placer(data(r).get('Veh Placed by')) for r in rows} - {''})
    expenses = [r for r in rows if r.get('report_scope') == 'Expense']
    amounts = sorted({float(r.get('amount') or 0) for r in expenses})
    defaults = dict(start=today.replace(day=1), end=today, record_type=TRIP_RECORDS,
                    vehicle='All', placer='All', ownership='Both', amount='All', heading='All',
                    without_evidence=False, order='↓', lr_number='', invoice_number='')
    saved_key = f'applied_records_filters_{user}'
    applied = {**defaults, **st.session_state.get(saved_key, {})}
    with st.form(f'records_filters_batch_{user}', border=False):
        a,b,c = st.columns(3)
        start = a.date_input('Records from', value=max(applied['start'], OPERATIONS_START), format='DD/MM/YYYY', min_value=OPERATIONS_START)
        end = b.date_input('Records to', value=max(applied['end'], OPERATIONS_START), format='DD/MM/YYYY', min_value=OPERATIONS_START)
        kind = c.selectbox('Record Type', RECORD_TYPES, index=RECORD_TYPES.index(applied['record_type']))
        a,b,c = st.columns(3)
        def select(column, label, options, field):
            value = applied[field]
            return column.selectbox(label, options, index=options.index(value) if value in options else 0,
                format_func=(lambda item: 'All' if item == 'All' else format_inr(item)) if label == 'By Amount' else str)
        vehicle_column = b if kind == TRIP_RECORDS and user != 'Ashok' else a
        vehicle = select(vehicle_column,'Vehicle no.',['All',*vehicles],'vehicle')
        placer, ownership, amount, heading = 'All', 'Both', 'All', 'All'
        if kind == TRIP_RECORDS:
            if user != 'Ashok':
                placer = select(a,'Vehicle placed by',['All',*placers],'placer')
                ownership = select(c,'Own or outside',['Both','Own','Outside'],'ownership')
        elif kind == DIRECT_EXPENSES:
            amount = select(b,'By Amount',['All',*amounts],'amount')
            heading = select(c,'Heading',['All',*direct_expense_headings(expenses)],'heading')
        a,b = st.columns(2)
        def identifier_select(column, label, field, values):
            options = ['', *sorted(({str(value).strip() for value in values if value}
                                    | {applied[field]}) - {''}, key=str.casefold)]
            return column.selectbox(
                label, options, index=options.index(applied[field]),
                format_func=lambda value: value or 'All', accept_new_options=True,
            )
        lr_number = identifier_select(a, 'LR No.', 'lr_number',
            [data(row).get('LR No.') for row in rows])
        invoice_number = identifier_select(b, 'Invoice No.', 'invoice_number',
            [row.get('invoice_number') or data(row).get('Invoice No.') for row in rows])
        submitted = st.form_submit_button('Apply Filters', type='primary')
    if submitted:
        if start > end:
            st.error('Records from must be on or before Records to. Previous filters remain applied.')
        else:
            applied = dict(start=start,end=end,record_type=kind,vehicle=vehicle,placer=placer,
                           ownership=ownership,amount=amount,heading=heading,without_evidence=False,order='↓',
                           lr_number=lr_number.strip(), invoice_number=invoice_number.strip())
            st.session_state[saved_key] = applied
    return applied


def filter_identifiers(rows, filters):
    """Case-insensitive partial identifier search, preserving full invoice numbers."""
    def matches(row):
        raw = row.get('dtr_data') or {}
        dtr = json.loads(raw) if isinstance(raw, str) else raw
        lr = str(dtr.get('LR No.') or '').strip().casefold()
        invoice = str(row.get('invoice_number') or dtr.get('Invoice No.') or '').strip().casefold()
        return (filters.get('lr_number', '').strip().casefold() in lr
                and filters.get('invoice_number', '').strip().casefold() in invoice)
    return [row for row in rows if matches(row)]
