"""UPI and Billtee ledger cards and trip clearance dialog."""
import hashlib
import html
import json
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from .balance_workspace import currency, today
from .branch_names import canonical_branch
from .invoice_display import dtr_invoice_text
from .pending_payments import data, payment_groups
from .payment_settlement import money


_ledger = components.declare_component(
    'oneshot_reimbursement_ledger', path=str(Path(__file__).with_name('reimbursement_ledger_component')))


def reimbursement_groups(trips, kind, queued, profiles, clearings):
    groups = payment_groups(trips, kind, queued, profiles)
    for group in groups:
        for item in group:
            original = money(item['amount'])
            cleared = min(original, money(clearings.get(item['trip']['request_number'], 0)))
            item['cleared'] = cleared
            item['outstanding'] = original - cleared
            item['ledger_status'] = ('Cleared' if not item['outstanding'] else
                                     'Partially cleared' if cleared else 'Pending')
    return groups


def trip_payload(item):
    trip = item['trip']
    raw = data(trip.get('dtr_data'))
    return {
        'id': trip['request_number'],
        'invoice': dtr_invoice_text(raw.get('Invoice No.') or trip.get('invoice_number')) or trip['request_number'],
        'date': str(trip['trip_date'])[:10],
        'branch': canonical_branch(trip.get('branch')),
        'vehicle': trip.get('vehicle_number') or '',
        'route': f"{trip.get('from_location') or ''} → {trip.get('to_location') or ''}",
        'original': int(money(item['amount']) * 100),
        'paid': int(item['cleared'] * 100),
        'outstanding': int(item['outstanding'] * 100),
        'status': item['ledger_status'],
    }


@st.dialog('Update in Ledger', width='large', dismissible=True, on_dismiss='ignore')
def update_reimbursement_ledger(name, kind, group, user, store, instance):
    st.markdown('''<style>
    [data-testid="stDialog"]:has(.reimbursement-popup-marker) [role="dialog"]{width:98vw!important;max-width:98vw!important;height:94dvh!important;max-height:94dvh!important;overflow:hidden!important;background:linear-gradient(125deg,#fff,#f8fbff)!important;border-radius:22px!important;padding:12px!important}
    [data-testid="stDialog"]:has(.reimbursement-popup-marker) [role="dialog"]>div:first-child{display:none!important}
    [data-testid="stDialog"]:has(.reimbursement-popup-marker) [role="dialog"] button[aria-label="Close"]{visibility:hidden!important}
    [data-testid="stDialog"]:has(.reimbursement-popup-marker) [role="dialog"]>div:last-child{padding:8px 10px!important}
    [data-testid="stDialog"]:has(.reimbursement-popup-marker) iframe{width:100%!important;height:calc(94dvh - 48px)!important;border:0!important}
    [data-testid="stDialog"]:has(.reimbursement-popup-marker) [data-testid="stVerticalBlock"]{gap:0!important}
    </style><span class="reimbursement-popup-marker"></span>''', unsafe_allow_html=True)
    rows = [trip_payload(item) for item in group]
    signature = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    result = _ledger(name=name, kind=kind, rows=rows, today=str(today()),
        start=min((row['date'] for row in rows), default=str(today())), signature=signature,
        response=st.session_state.get('reimbursement_response_' + instance),
        key='reimbursement_component_' + instance, default=None)
    if not isinstance(result, dict):
        return
    nonce = result.get('nonce')
    if not isinstance(nonce, str) or not nonce or len(nonce) > 150 or nonce == st.session_state.get('reimbursement_action_' + instance):
        return
    st.session_state['reimbursement_action_' + instance] = nonce
    if result.get('action') == 'close':
        st.rerun()
    if result.get('action') != 'clear_selected':
        st.session_state['reimbursement_response_' + instance] = {'nonce': nonce, 'error': 'Sending trips for RTGS is temporarily unavailable.'}
        st.rerun(scope='fragment')
    numbers = result.get('numbers')
    by_number = {item['trip']['request_number']: item['trip'] for item in group}
    if not isinstance(numbers, list) or not numbers or len(numbers) != len(set(numbers)) or not set(numbers) <= set(by_number):
        st.session_state['reimbursement_response_' + instance] = {'nonce': nonce, 'error': 'Select valid trips from this group.'}
        st.rerun(scope='fragment')
    try:
        count = store.clear_reimbursements(user, kind, {number: by_number[number]['updated_at'] for number in numbers})
    except ValueError as exc:
        st.session_state['reimbursement_response_' + instance] = {'nonce': nonce, 'error': str(exc)}
        st.rerun(scope='fragment')
    else:
        st.session_state['pending_payment_notice'] = f'{count} {kind.upper() if kind == "upi" else "Billtee"} trip(s) cleared. Amounts and statuses are updated.'
        st.rerun()


def render_reimbursement_cards(user, trips, kind, store):
    labels = {'upi': 'UPI', 'billtee': 'Billtee'}
    title = labels[kind]
    profiles = store.pending_upi_profiles(user)
    queued = store.list_upi_payments() if kind == 'upi' else store.list_billtee_payments()
    clearings = store.reimbursement_clearings(user, kind)
    groups = reimbursement_groups(trips, kind, queued, profiles, clearings)
    visible = [group for group in groups if any(item['outstanding'] > 0 for item in group)]
    visible.sort(key=lambda group: -sum(item['outstanding'] for item in group))
    count = sum(item['outstanding'] > 0 for group in visible for item in group)
    outstanding = sum((item['outstanding'] for group in visible for item in group), money(0))
    st.markdown('''<style>
    .reimbursement-heading{display:flex;align-items:center;gap:18px;margin:15px 0 23px}.reimbursement-heading-icon{display:grid;place-items:center;width:66px;height:66px;border-radius:18px;background:#e4edff;color:#0761ef;font-size:34px}.reimbursement-heading h2{margin:0;font-size:32px;line-height:1.15}.reimbursement-heading p{margin:3px 0 0;color:#445b84;font-size:15px}
    .reimbursement-summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;margin:20px 0}.reimbursement-stat{position:relative;overflow:hidden;display:flex;align-items:center;gap:24px;min-height:145px;padding:26px;border:1px solid #dbe5f6;border-radius:20px;background:linear-gradient(125deg,#fff,#f4f8ff)}.reimbursement-stat.red{background:linear-gradient(125deg,#fff,#fff3f5)}.reimbursement-stat:after{content:"";position:absolute;right:-20px;bottom:-48px;width:40%;height:110px;border-radius:80% 20% 0 0;background:#e6efff;transform:rotate(-14deg)}.reimbursement-stat.red:after{background:#fbe5ea}.reimbursement-stat-icon{display:grid;place-items:center;flex:none;width:58px;height:58px;border-radius:17px;background:#ffe8ef;color:#cb153c;font-size:30px}.reimbursement-stat.red .reimbursement-stat-icon{background:#fff0df;color:#f18a00}.reimbursement-stat-copy{position:relative;z-index:1}.reimbursement-stat-copy span{display:block;font-weight:700}.reimbursement-stat-copy strong{display:block;font-size:34px;margin:7px 0;color:#101936}.reimbursement-stat.red strong{color:#a80c1a}.reimbursement-stat-copy small{color:#71819f}
    [class*="st-key-reimbursement_card_"]{min-height:95px;margin:13px 0;padding:17px 25px;border:1px solid #d8e4f7;border-radius:18px;background:linear-gradient(125deg,#fff,#f9fbff);box-shadow:0 4px 15px #234e9a0b}.reimbursement-person{display:flex;align-items:center;gap:20px}.reimbursement-avatar{display:grid;place-items:center;flex:none;width:59px;height:59px;border-radius:50%;background:#d3f3e7;border:1px solid #aae1ca;color:#107b59;font-size:28px;font-weight:800}.reimbursement-person strong{display:block;font-size:21px;color:#101936}.reimbursement-person small{color:#667797;font-size:14px}.reimbursement-total{border-left:1px solid #bdcce9;padding-left:26px}.reimbursement-total small{display:block;color:#51658c}.reimbursement-total strong{display:block;color:#101936;font-size:23px}[class*="st-key-reimbursement_card_"] button{border:1px solid #9fbcff!important;background:#fff!important;color:#075dff!important;border-radius:11px!important;font-weight:700!important;min-height:45px!important;width:100%!important}
    @media(max-width:700px){.reimbursement-summary{grid-template-columns:1fr}[class*="st-key-reimbursement_card_"] [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}[class*="st-key-reimbursement_card_"] [data-testid="stColumn"]{width:100%!important;min-width:100%!important}.reimbursement-total{border-left:0;padding-left:0}.reimbursement-heading h2{font-size:26px}}
    </style>''', unsafe_allow_html=True)
    st.markdown('<div class="reimbursement-heading"><div class="reimbursement-heading-icon">▣</div><div><h2>Ledger</h2><p>Review, update and send Balance Payable, UPI and Billtee payments.</p></div></div>', unsafe_allow_html=True)
    columns = st.columns([1.6, .85, .9], gap='small')
    for column, label, option, icon in zip(columns, ['Balance Payable', 'UPI', 'Billtee'], ['balance', 'upi', 'billtee'], ['local_shipping', 'directions_car', 'receipt_long']):
        column.button(label, icon=f':material/{icon}:', type='primary' if option == kind else 'secondary',
            use_container_width=True, key=f'reimbursement_kind_{option}',
            on_click=st.session_state.update, args=({'pending_kind_card': option},))
    st.markdown(f'<div class="reimbursement-summary"><div class="reimbursement-stat"><div class="reimbursement-stat-icon">▤</div><div class="reimbursement-stat-copy"><span>Pending {title} Requests</span><strong>{count}</strong><small>Trip reimbursements awaiting clearance</small></div></div><div class="reimbursement-stat red"><div class="reimbursement-stat-icon">⌛</div><div class="reimbursement-stat-copy"><span>Outstanding {title} Amount</span><strong>{html.escape(currency(outstanding))}</strong></div></div></div>', unsafe_allow_html=True)
    if not visible:
        st.info(f'No outstanding {title} trips.')
        return
    for group in visible:
        name = group[0]['name']
        key = hashlib.sha256((kind + name + str(group[0]['profile'])).encode()).hexdigest()[:16]
        pending = [item for item in group if item['outstanding'] > 0]
        last = max(item['trip']['trip_date'] for item in group)
        total = sum((item['outstanding'] for item in group), money(0))
        with st.container(key=f'reimbursement_card_{key}'):
            identity, amount_col, action = st.columns([1.7, .7, .62], gap='medium', vertical_alignment='center')
            identity.markdown(f'<div class="reimbursement-person"><span class="reimbursement-avatar">{html.escape(name[:1].upper())}</span><div><strong>{html.escape(name)}</strong><small>{len(pending)} request{"s" if len(pending) != 1 else ""} · Last entry: {last:%d %b %Y}</small></div></div>', unsafe_allow_html=True)
            amount_col.markdown(f'<div class="reimbursement-total"><small>{title} Outstanding</small><strong>{html.escape(currency(total))}</strong></div>', unsafe_allow_html=True)
            if action.button('Update in Ledger', icon=':material/edit:', key=f'reimbursement_update_{key}', use_container_width=True):
                update_reimbursement_ledger(name, kind, group, user, store, uuid.uuid4().hex)
