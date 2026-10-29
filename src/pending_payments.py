"""Sid-only grouped review of unsent trip balance and UPI reimbursements."""
import json
import math
import hashlib
import html
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


def send_reviewed_group(selected, kind, user, store):
    if not selected:
        st.warning('Select at least one Pending trip to send.')
        return
    try:
        count = store.send_pending_payments(selected, kind, user)
    except ValueError as exc:
        st.error(str(exc))
    else:
        st.session_state['pending_payment_notice'] = f'Sent {count} payment(s) to RTGS.'
        st.rerun()


def render_pending_payments(user, trips, balance_requests, upi_requests, store):
    if user != 'Sid':
        return
    st.markdown('''<style>
    .st-key-pending_payments_surface{color:#101a32}
    .pp-intro{display:flex;align-items:center;gap:18px;margin:22px 0 24px}.pp-icon{display:grid;place-items:center;width:56px;height:56px;border-radius:15px;background:#ddf7ed;color:#147453;font-size:34px;font-weight:800}.pp-intro h2{margin:0;padding:0;color:#0b1530;font-size:26px}.pp-intro p{margin:5px 0 0;color:#72809c;font-size:14px}
    .st-key-pending_toolbar [data-testid="stHorizontalBlock"]{align-items:center}
    .st-key-pending_toolbar button{white-space:nowrap;font-size:12px!important;border:1px solid #dbe5ee;border-radius:24px;background:#fff;box-shadow:none;min-height:42px;padding:7px 14px}
    .st-key-pending_toolbar button[kind="primary"]{background:#e1f7ec!important;color:#105d46!important;border:1px solid #a4ddc9!important;box-shadow:none!important}
    .st-key-pending_toolbar [data-baseweb="input"],.st-key-pending_toolbar [data-baseweb="select"]{font-size:12px}
    [class*="st-key-pending_card_"]{background:linear-gradient(125deg,#fff,#fbfdff)!important;border:1px solid #e2eaf2!important;border-radius:16px!important;padding:12px!important;box-shadow:0 6px 20px rgba(30,60,90,.035)!important;margin-bottom:10px}
    [class*="st-key-pending_card_"] [data-testid="stHorizontalBlock"]{align-items:center}
    .pp-identity{display:flex;gap:13px;align-items:center;min-height:50px}.pp-avatar{display:grid;place-items:center;flex-shrink:0;width:45px;height:45px;border-radius:50%;background:#d4f4e7;border:1px solid #b8e6d4;color:#0d7153;font-size:21px;font-weight:700}.pp-name{color:#0d1731;font-weight:750;font-size:17px;overflow-wrap:anywhere}.pp-meta{color:#7b86a1;font-size:12px;margin-top:3px}.pp-total span{display:block;color:#7b86a1;font-size:12px}.pp-total strong{color:#101a32;font-size:20px}
    [class*="st-key-pending_send_"] button,[class*="st-key-pending_group_"] [data-testid="stFormSubmitButton"] button{background:#267b5f!important;color:white!important;border:0!important;border-radius:11px!important;box-shadow:none!important;font-size:12px!important;white-space:nowrap;min-height:40px!important}
    [class*="st-key-pending_send_"] button:disabled{opacity:.4}
    [class*="st-key-pending_expand_"] button{border:0!important;border-radius:50%!important;width:32px!important;min-width:32px!important;min-height:32px!important;padding:0!important;background:#f4f7fb!important;box-shadow:none!important}
    [class*="st-key-pending_card_"] [data-testid="stForm"]{border:0;padding:0}
    [class*="st-key-pending_card_"] [data-testid="stDataFrame"]{box-shadow:none!important;border-radius:10px!important}
    </style><div class="pp-intro"><div class="pp-icon">₹</div><div><h2>Pending Payments</h2><p>Review and send pending Balance Payments or UPI payments.</p></div></div>''', unsafe_allow_html=True)
    kind = st.session_state.get('pending_kind_card', 'balance')
    with st.container(key='pending_toolbar'):
        balance_col, upi_col, search_col, branch_col, status_col, sort_col = st.columns([2.1,2.2,1.7,1.1,1.1,1.6], gap='small')
        if balance_col.button('Balance Payments (Transporters)', icon=':material/local_shipping:',
                              type='primary' if kind == 'balance' else 'secondary', use_container_width=True):
            st.session_state['pending_kind_card'] = 'balance'; st.rerun()
        if upi_col.button('UPI Payments (Vehicles / Placed by)', icon=':material/directions_car:',
                          type='primary' if kind == 'upi' else 'secondary', use_container_width=True):
            st.session_state['pending_kind_card'] = 'upi'; st.rerun()
        search = search_col.text_input('Search transporter / payer', placeholder='Search transporter…' if kind == 'balance' else 'Search payer…',
                                       label_visibility='collapsed', key='pending_search')
        branch = branch_col.selectbox('Branch', ['All Branches','Andheri','Pune','Vadodara','Wada'], label_visibility='collapsed', key='pending_branch')
        status = status_col.selectbox('Status', ['All Status','Pending','Sent to RTGS','RTGS Done'], label_visibility='collapsed', key='pending_card_status')
        sort = sort_col.selectbox('Sort by', ['Total Amount (High to Low)','Name'], label_visibility='collapsed', key='pending_sort')
    profiles = store.pending_upi_profiles(user) if kind == 'upi' else {}
    groups = payment_groups(trips, kind, balance_requests if kind == 'balance' else upi_requests, profiles)
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
    page_size = 20
    pages = max(1, (len(filtered) + page_size - 1) // page_size)
    page = 1
    if pages > 1:
        page = st.selectbox('Payment groups page', range(1, pages + 1), format_func=lambda value:f'Page {value} of {pages}', key=f'pending_page_{kind}_{pages}')
    for index, group in enumerate(filtered[(page-1)*page_size:page*page_size]):
        first = group[0]
        total = sum(item['amount'] for item in group)
        profile = first['profile']
        configured = all(str(profile.get(field) or '').strip() for field in ('BNF_NAME','BENE_ACC_NO','BENE_IFSC'))
        signature = '|'.join(f"{item['trip']['request_number']}:{item['trip'].get('updated_at')}:{item['status']}" for item in group)
        key = hashlib.sha256((kind + signature).encode()).hexdigest()[:16]
        open_key = f'pending_open_{key}'
        expanded = st.session_state.get(open_key, index == 0)
        selected_all = {item['trip']['request_number']:item['trip'].get('updated_at') for item in group if item['status'] == 'Pending'}
        with st.container(key=f'pending_card_{key}'):
            arrow, identity, figure, action, more = st.columns([.35,4.1,2.5,1.65,.45], gap='small', vertical_alignment='center')
            if arrow.button('', icon=':material/keyboard_arrow_down:' if expanded else ':material/chevron_right:',
                            key=f'pending_expand_{key}', help='Collapse trips' if expanded else 'View trips'):
                st.session_state[open_key] = not expanded; st.rerun()
            last_trip = max(str(item['trip'].get('trip_date') or '')[:10] for item in group)
            try:
                last_trip = pd.Timestamp(last_trip).strftime('%d %b %Y')
            except (ValueError, TypeError):
                last_trip = 'Not specified'
            identity.markdown(f'<div class="pp-identity"><div class="pp-avatar">{html.escape(first["name"][:1].upper())}</div><div><div class="pp-name">{html.escape(first["name"])}</div><div class="pp-meta">{len(group)} trips · Last trip: {html.escape(last_trip)}</div></div></div>', unsafe_allow_html=True)
            figure.markdown(f'<div class="pp-total"><span>Total {"Balance" if kind == "balance" else "UPI"} Amount</span><strong>{format_inr(total)}</strong></div>', unsafe_allow_html=True)
            if action.button('Send for RTGS', icon=':material/send:', key=f'pending_send_{key}', type='primary',
                             disabled=not configured or not selected_all, help='Send all pending trips in this group to RTGS', use_container_width=True):
                send_reviewed_group(selected_all, kind, user, store)
            with more.popover('⋯', help='Beneficiary details'):
                st.write(f"Beneficiary: {profile.get('BNF_NAME') or 'Not configured'}")
                st.write(f"Account: {profile.get('BENE_ACC_NO') or 'Not configured'}")
                st.write(f"IFSC: {profile.get('BENE_IFSC') or 'Not configured'}")
                st.caption('Accounts are grouped separately when beneficiary details differ.')
            if not expanded:
                continue
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
            with st.form(f'pending_group_{key}'):
                frame = pd.DataFrame(rows)
                edited = st.data_editor(frame, hide_index=True, width='stretch',
                    disabled=[col for col in frame if col != 'Select'], key=f'pending_selection_{key}')
                send = st.form_submit_button('Send selected for RTGS', type='primary', disabled=not configured)
            if send:
                selected = {row['Record']:by_number[row['Record']].get('updated_at')
                            for row in edited.to_dict('records') if row['Select'] and row['Status'] == 'Pending'}
                send_reviewed_group(selected, kind, user, store)
