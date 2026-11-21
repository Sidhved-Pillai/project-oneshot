"""Filter controls submitted as one request rather than per-field reruns."""
import datetime as dt
import json

import streamlit as st

from .record_filters_v3 import RECORD_TYPES, TRIP_RECORDS, DIRECT_EXPENSES, direct_expense_headings
from .vehicle_normalization import canonical_vehicle_number
from .vehicle_placer import canonical_vehicle_placer
from .number_format import format_inr
from .operational_dates_v2 import OPERATIONS_START
from .route_expense_export import route_export_row
from .expense_amounts import expense_amounts
from .record_lookup import identifier_matches


def render_filters(rows, user, today):
    designed_records = user in {'Shyam', 'Sid', 'Nikhat', 'Vijay', 'Ajit', 'Nitish', 'Gopal', 'Manish', 'Ashok'}
    def data(row):
        raw = row.get('dtr_data') or {}
        return json.loads(raw) if isinstance(raw, str) else raw
    vehicles = sorted({canonical_vehicle_number(r.get('vehicle_number')) for r in rows} - {''})
    placers = sorted({canonical_vehicle_placer(data(r).get('Veh Placed by')) for r in rows} - {''})
    expenses = [r for r in rows if r.get('report_scope') == 'Expense']
    amounts = sorted({float(value) for row in expenses for value in expense_amounts(row)})
    expenses += [projected for row in rows if (projected := route_export_row(row)) is not None]
    defaults = dict(start=today.replace(day=1), end=today, record_type=TRIP_RECORDS,
                    vehicle='All', placer='All', ownership='Both', amount='All', heading='All',
                    without_evidence=False, order='↓', lr_number='', invoice_number='')
    saved_key = f'applied_records_filters_{user}'
    applied = {**defaults, **st.session_state.get(saved_key, {})}
    def widget_key(field):
        key = f'records_filter_draft_{user}_{field}'
        st.session_state.setdefault(key, applied[field])
        return key
    def reset_filters():
        st.session_state[saved_key] = dict(defaults)
        for field, value in defaults.items():
            st.session_state[f'records_filter_draft_{user}_{field}'] = value
        st.session_state['records_result_page'] = 1
    with st.form(f'records_filters_batch_{user}', border=False):
        if designed_records:
            st.markdown('<div class="sr-filter-title">&#9661; &nbsp; Filters</div>', unsafe_allow_html=True)
            if user == 'Ashok':
                c,a,b,vehicle_col = st.columns(4)
                placer_col = None
            else:
                c,a,b,placer_col,vehicle_col = st.columns(5)
        else:
            a,b,c = st.columns(3)
        start = a.date_input('Date From' if designed_records else 'Records from', key=widget_key('start'), format='DD/MM/YYYY', min_value=OPERATIONS_START)
        end = b.date_input('Date To' if designed_records else 'Records to', key=widget_key('end'), format='DD/MM/YYYY', min_value=OPERATIONS_START)
        kind = c.selectbox('Record Type', RECORD_TYPES, key=widget_key('record_type'))
        if designed_records:
            if user == 'Ashok':
                lr_col,invoice_col,reset_col,apply_col = st.columns([1,1,.48,.72])
            else:
                own_col,lr_col,invoice_col,reset_col,apply_col = st.columns([1,1,1,.48,.72])
                a,b,c = placer_col,vehicle_col,own_col
        else:
            a,b,c = st.columns(3)
        def select(column, label, options, field):
            key = widget_key(field)
            if st.session_state[key] not in options:
                st.session_state[key] = options[0]
            return column.selectbox(label, options, key=key,
                format_func=(lambda item: 'All' if item == 'All' else format_inr(item)) if label == 'By Amount' else str)
        vehicle_column = vehicle_col if designed_records else (b if kind == TRIP_RECORDS and user != 'Ashok' else a)
        vehicle = select(vehicle_column,'Vehicle no.',['All',*vehicles],'vehicle')
        placer, ownership, amount, heading = 'All', 'Both', 'All', 'All'
        if kind == TRIP_RECORDS:
            if user != 'Ashok':
                placer = select(a,'Vehicle placed by',['All',*placers],'placer')
                ownership = select(c,'Own or outside',['Both','Own','Outside'],'ownership')
        elif kind == DIRECT_EXPENSES:
            if user == 'Ashok' and designed_records:
                amount_col, heading_col = st.columns(2)
            else:
                amount_col, heading_col = (placer_col if designed_records else b), c
            amount = select(amount_col,'By Amount',['All',*amounts],'amount')
            heading = select(heading_col,'Heading',['All',*direct_expense_headings(expenses)],'heading')
        if designed_records:
            a,b = lr_col,invoice_col
        else:
            a,b = st.columns(2)
        def identifier_select(column, label, field, values):
            key = widget_key(field)
            options = ['', *sorted(({str(value).strip() for value in values if value}
                                    | {applied[field], st.session_state[key]}) - {''}, key=str.casefold)]
            return column.selectbox(
                label, options, key=key,
                format_func=lambda value: value or 'All', accept_new_options=True,
            )
        lr_number = identifier_select(a, 'LR No.', 'lr_number',
            [data(row).get('LR No.') for row in rows])
        invoice_number = identifier_select(b, 'Invoice No.', 'invoice_number',
            [row.get('invoice_number') or data(row).get('Invoice No.') for row in rows])
        if designed_records:
            reset_col.form_submit_button('Reset', on_click=reset_filters, use_container_width=True)
            submitted = apply_col.form_submit_button('Apply Filters', type='primary', use_container_width=True)
        else:
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
    return [row for row in rows if identifier_matches(row, filters)]
