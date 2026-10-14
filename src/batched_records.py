"""Filter controls submitted as one request rather than per-field reruns."""
import datetime as dt
import json

import streamlit as st

from .record_filters import RECORD_TYPES, TRIP_RECORDS, DIRECT_EXPENSES, direct_expense_headings
from .vehicle_normalization import canonical_vehicle_number
from .vehicle_placer import canonical_vehicle_placer
from .number_format import format_inr


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
                    without_evidence=False, order='↓')
    saved_key = f'applied_records_filters_{user}'
    applied = st.session_state.get(saved_key, defaults)
    with st.form(f'records_filters_batch_{user}', border=False):
        a,b,c = st.columns(3)
        start = a.date_input('Records from', value=applied['start'], format='DD/MM/YYYY')
        end = b.date_input('Records to', value=applied['end'], format='DD/MM/YYYY')
        kind = c.selectbox('Record Type', RECORD_TYPES, index=RECORD_TYPES.index(applied['record_type']))
        a,b,c = st.columns(3)
        def select(column, label, options, field):
            value = applied[field]
            return column.selectbox(label, options, index=options.index(value) if value in options else 0,
                format_func=(lambda item: 'All' if item == 'All' else format_inr(item)) if label == 'By Amount' else str)
        vehicle_column = b if kind == TRIP_RECORDS and user not in {'Ashok','Ajit'} else a
        vehicle = select(vehicle_column,'Vehicle no.',['All',*vehicles],'vehicle')
        placer, ownership, amount, heading = 'All', 'Both', 'All', 'All'
        if kind == TRIP_RECORDS:
            if user not in {'Ashok','Ajit'}:
                placer = select(a,'Vehicle placed by',['All',*placers],'placer')
                ownership = select(c,'Own or outside',['Both','Own','Outside'],'ownership')
        elif kind == DIRECT_EXPENSES:
            amount = select(b,'By Amount',['All',*amounts],'amount')
            heading = select(c,'Heading',['All',*direct_expense_headings(expenses)],'heading')
        submitted = st.form_submit_button('Apply Filters', type='primary')
    if submitted:
        if start > end:
            st.error('Records from must be on or before Records to. Previous filters remain applied.')
        else:
            applied = dict(start=start,end=end,record_type=kind,vehicle=vehicle,placer=placer,
                           ownership=ownership,amount=amount,heading=heading,without_evidence=False,order='↓')
            st.session_state[saved_key] = applied
    return applied
