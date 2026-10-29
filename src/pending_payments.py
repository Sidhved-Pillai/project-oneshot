"""Sid-only grouped review of unsent trip balance and UPI reimbursements."""
import json
import math
from collections import defaultdict

import pandas as pd
import streamlit as st

from .branch_names import canonical_branch
from .number_format import format_inr
from .vehicle_placer import canonical_vehicle_placer


def data(value):
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value or '{}')
    except (TypeError, ValueError):
        return {}


def amount(value):
    try:
        value = float(value or 0)
        return value if math.isfinite(value) else 0.0
    except (TypeError, ValueError):
        return 0.0


def payment_groups(trips, kind, requests, profiles):
    groups = defaultdict(list)
    for trip in trips:
        if trip.get('report_scope') == 'Expense' or trip.get('is_archived') or trip.get('status') == 'Cancelled':
            continue
        raw = data(trip.get('dtr_data'))
        if kind == 'balance':
            if str(trip.get('ownership_type') or '').strip().lower().startswith('own'):
                continue
            value = amount(trip.get('balance_amount'))
            profile = data(trip.get('rtgs_data'))
            name = str(trip.get('transporter_name') or raw.get('Transporter Name') or 'Transporter not specified').strip()
            owner = ''
            profile = {**profile, 'BNF_NAME':profile.get('BNF_NAME') or trip.get('beneficiary_name','')}
        else:
            value = amount(trip.get('upi'))
            owner = str(trip.get('created_by') or '').strip()
            profile = profiles.get(owner, {})
            name = canonical_vehicle_placer(raw.get('Veh Placed by')) or owner or 'Payer not specified'
        if value <= 0:
            continue
        payment = requests.get(trip.get('request_number'))
        status = 'RTGS Done' if payment and payment.get('rtgs_done') else 'Sent to RTGS' if payment else 'Pending'
        # Keep different beneficiary accounts separate even when transporter names match.
        key = (name.casefold(), owner, *(str(profile.get(field) or '').strip() for field in ('BNF_NAME','BENE_ACC_NO','BENE_IFSC')))
        groups[key].append({'trip':trip, 'name':name, 'profile':profile, 'amount':value, 'status':status})
    return list(groups.values())


def render_pending_payments(user, trips, balance_requests, upi_requests, store):
    if user != 'Sid':
        return
    st.markdown('## Pending Payments')
    st.caption('Review transporter balances and personal UPI reimbursements, then send selected trips to RTGS.')
    kind_label = st.segmented_control('Payment type', ['Balance Payments (Transporters)', 'UPI Payments (Placed by)'],
                                       default='Balance Payments (Transporters)', key='pending_kind')
    kind = 'upi' if kind_label == 'UPI Payments (Placed by)' else 'balance'
    profiles = store.pending_upi_profiles(user) if kind == 'upi' else {}
    groups = payment_groups(trips, kind, balance_requests if kind == 'balance' else upi_requests, profiles)
    with st.form('pending_payment_filters', border=False):
        search_col, branch_col, status_col, sort_col = st.columns([2,1,1,1.5])
        search = search_col.text_input('Search transporter / payer', key='pending_search')
        branch = branch_col.selectbox('Branch', ['All Branches','Andheri','Pune','Vadodara','Wada'], key='pending_branch')
        status = status_col.selectbox('Status', ['Pending','Sent to RTGS','RTGS Done','All Status'], key='pending_status')
        sort = sort_col.selectbox('Sort by', ['Total Amount (High to Low)','Name'], key='pending_sort')
        st.form_submit_button('Apply Filters')
    filtered = []
    for group in groups:
        matching = [item for item in group
                    if (branch == 'All Branches' or canonical_branch(item['trip'].get('branch')) == branch)
                    and (status == 'All Status' or item['status'] == status)]
        if matching and (not search or search.casefold() in (matching[0]['name'] + ' ' + str(matching[0]['profile'].get('BNF_NAME',''))).casefold()):
            filtered.append(matching)
    filtered.sort(key=lambda group: -sum(item['amount'] for item in group) if sort.startswith('Total') else group[0]['name'].casefold())
    st.caption(f"{sum(len(group) for group in filtered)} trips · {len(filtered)} groups · {format_inr(sum(item['amount'] for group in filtered for item in group))}")
    if not filtered:
        st.info('No payments match these filters.')
    for index, group in enumerate(filtered):
        first = group[0]
        total = sum(item['amount'] for item in group)
        with st.expander(f"{first['name']} · {len(group)} trips · {format_inr(total)}"):
            profile = first['profile']
            st.write(f"Beneficiary: {profile.get('BNF_NAME') or 'Not configured'}")
            st.write(f"Account: {profile.get('BENE_ACC_NO') or 'Not configured'} · IFSC: {profile.get('BENE_IFSC') or 'Not configured'}")
            configured = all(str(profile.get(field) or '').strip() for field in ('BNF_NAME','BENE_ACC_NO','BENE_IFSC'))
            if not configured:
                st.warning('Beneficiary bank details must be configured before sending this group.')
            rows = []
            by_number = {}
            for item in group:
                trip = item['trip']; number = trip['request_number']; by_number[number] = trip
                rows.append({'Select':False, 'Record':number, 'Date':trip.get('trip_date'),
                    'Branch':canonical_branch(trip.get('branch')), 'Route':f"{trip.get('from_location') or ''} → {trip.get('to_location') or ''}",
                    'Vehicle No.':trip.get('vehicle_number'), 'LR No.':data(trip.get('dtr_data')).get('LR No.',''),
                    'Invoice No.':trip.get('invoice_number'), 'Freight':amount(trip.get('transporter_freight')),
                    'Paid':amount(trip.get('total_advance')), 'Balance' if kind == 'balance' else 'UPI':item['amount'], 'Status':item['status']})
            signature = '|'.join(f"{item['trip']['request_number']}:{item['trip'].get('updated_at')}:{item['status']}" for item in group)
            import hashlib
            key = hashlib.sha256((kind + signature).encode()).hexdigest()[:16]
            with st.form(f'pending_group_{key}'):
                frame = pd.DataFrame(rows)
                edited = st.data_editor(frame, hide_index=True, width='stretch',
                    disabled=[col for col in frame if col != 'Select'], key=f'pending_selection_{key}')
                send = st.form_submit_button('Send selected for RTGS', type='primary', disabled=not configured)
            if send:
                selected = {row['Record']:by_number[row['Record']].get('updated_at')
                            for row in edited.to_dict('records') if row['Select'] and row['Status'] == 'Pending'}
                if not selected:
                    st.warning('Select at least one Pending trip to send.')
                else:
                    try:
                        count = store.send_pending_payments(selected, kind, user)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state['pending_payment_notice'] = f'Sent {count} payment(s) to RTGS.'
                        st.rerun()
