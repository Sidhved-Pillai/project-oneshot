"""Stable Ledger selector and outstanding amount cards shared by all payment modes."""
import html

import streamlit as st

from .balance_workspace import currency
from .payment_settlement import money


def outstanding_totals(trips, balance_rows, upi_clearings, billtee_clearings):
    from .pending_payments import data
    totals = {'balance': sum((money(row['_outstanding']) for row in balance_rows), money(0)),
              'upi': money(0), 'billtee': money(0)}
    for trip in trips:
        if trip.get('report_scope') == 'Expense' or trip.get('is_archived') or trip.get('status') == 'Cancelled':
            continue
        number = trip['request_number']
        totals['upi'] += max(money(0), money(trip.get('upi')) - money(upi_clearings.get(number, 0)))
        totals['billtee'] += max(money(0), money(data(trip.get('dtr_data')).get('Billtee')) - money(billtee_clearings.get(number, 0)))
    return totals


def render_ledger_overview(kind, totals):
    st.markdown('''<style>
    .ledger-overview-heading{display:flex;align-items:center;gap:18px;margin:15px 0 24px}.ledger-overview-icon{display:grid;place-items:center;width:66px;height:66px;border-radius:18px;background:#e4edff;color:#0761ef;font-size:34px}.ledger-overview-heading h2{margin:0;font-size:32px;line-height:1.15;color:#101936}.ledger-overview-heading p{margin:5px 0 0;color:#445b84;font-size:15px}
    .st-key-ledger_selector{border:1px solid #bcd0ff;border-radius:999px;background:#fff;padding:0!important;margin-bottom:20px}.st-key-ledger_selector [data-testid="stHorizontalBlock"]{gap:0!important}.st-key-ledger_selector [data-testid="stColumn"]{min-width:0!important}.st-key-ledger_selector button{width:100%!important;min-height:54px!important;border:0!important;border-radius:999px!important;background:transparent!important;color:#101936!important;box-shadow:none!important;font-weight:700!important}.st-key-ledger_selector button[kind="primary"]{background:linear-gradient(110deg,#2187ff,#0052f5)!important;color:#fff!important;box-shadow:0 4px 10px #0053ee2b!important}.st-key-ledger_selector [data-testid="stColumn"]:not(:last-child){border-right:1px solid #c8d6f5}
    .ledger-overview-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin:12px 0 24px}.ledger-overview-card{position:relative;overflow:hidden;display:flex;align-items:center;gap:22px;min-height:152px;border:1px solid #dbe5f6;border-radius:20px;padding:23px 26px;background:linear-gradient(125deg,#fff,#f1fbf7)}.ledger-overview-card.upi{background:linear-gradient(125deg,#fff,#fff3f5)}.ledger-overview-card.billtee{background:linear-gradient(125deg,#fff,#f2f7ff)}.ledger-overview-card:after{content:"";position:absolute;right:-22px;bottom:-48px;width:42%;height:100px;background:#ddf5e9;border-radius:80% 20% 0 0;transform:rotate(-14deg)}.ledger-overview-card.upi:after{background:#fce1e7}.ledger-overview-card.billtee:after{background:#e1ecff}.ledger-overview-symbol{position:relative;z-index:1;display:grid;place-items:center;flex:none;width:60px;height:60px;border-radius:17px;background:#dff5e9;color:#087d4d;font-size:32px}.ledger-overview-card.upi .ledger-overview-symbol{background:#ffe2e8;color:#c7273c}.ledger-overview-card.billtee .ledger-overview-symbol{background:#e1edff;color:#075fe9}.ledger-overview-copy{position:relative;z-index:1;min-width:0}.ledger-overview-copy span{display:block;font-size:17px;font-weight:700;color:#101936}.ledger-overview-copy strong{display:block;margin:7px 0;font-size:clamp(24px,2.3vw,35px);line-height:1.15;color:#101936;white-space:nowrap}.ledger-overview-copy small{color:#667c9f;font-size:13px}
    @media(max-width:800px){.ledger-overview-cards{grid-template-columns:1fr;gap:10px}.ledger-overview-card{min-height:110px}.ledger-overview-copy strong{font-size:23px}.st-key-ledger_selector button{font-size:12px!important;padding:5px!important}.ledger-overview-heading h2{font-size:26px}}
    </style><div class="ledger-overview-heading"><div class="ledger-overview-icon">▣</div><div><h2>Ledger</h2><p>Review, update and send Balance Payable, UPI and Billtee payments.</p></div></div>''', unsafe_allow_html=True)
    with st.container(key='ledger_selector'):
        cols = st.columns(3, gap='small')
        for column, option, label, icon in zip(cols, ('balance', 'upi', 'billtee'),
            ('Balance Payable', 'UPI', 'Billtee'), ('local_shipping', 'directions_car', 'receipt_long')):
            column.button(label, icon=f':material/{icon}:', type='primary' if kind == option else 'secondary',
                use_container_width=True, key=f'ledger_overview_{option}',
                on_click=st.session_state.update, args=({'pending_kind_card': option},))
    cards = [
        ('balance', '▤', 'Balance Payable To Clear', 'Total balance payment pending'),
        ('upi', '▣', 'UPI To Clear', 'Total UPI amount pending'),
        ('billtee', '▥', 'Billtee To Clear', 'Total Billtee amount pending'),
    ]
    st.markdown('<div class="ledger-overview-cards">' + ''.join(
        f'<article class="ledger-overview-card {option}"><div class="ledger-overview-symbol">{icon}</div>'
        f'<div class="ledger-overview-copy"><span>{label}</span><strong>{html.escape(currency(totals[option]))}</strong><small>{description}</small></div></article>'
        for option, icon, label, description in cards) + '</div>', unsafe_allow_html=True)
