"""Presentation for Shyam's Records workspace; no persistence or filter logic."""
from html import escape
import streamlit as st
from .number_format import format_inr


def styles():
    st.markdown('''<style>
.st-key-shyam_records{color:#101944}
.st-key-shyam_records [data-testid="stVerticalBlock"]{gap:.65rem}
.st-key-shyam_records_filters,.st-key-shyam_records_table{background:linear-gradient(120deg,#fff,#f5f8ff);border:1px solid #d4dfff!important;border-radius:18px!important;padding:16px!important;box-shadow:0 4px 14px #1555cc08}
.st-key-shyam_records label p{font-size:14px!important;color:#111b48}
.st-key-shyam_records [data-testid="stForm"]{border:0;padding:0}
.st-key-shyam_records [data-testid="stHorizontalBlock"]{gap:12px}
.st-key-shyam_records_table [data-testid="stHorizontalBlock"]{min-width:1250px;align-items:center}
.st-key-shyam_records_table [data-testid="stHorizontalBlock"] p{font-size:13px;overflow-wrap:anywhere}
.st-key-shyam_records_table [data-testid="stHorizontalBlock"]{border-bottom:1px solid #e5eafa;padding:5px 0}
.st-key-shyam_records_table [data-testid="stHorizontalBlock"]:first-child{background:#e9edfc;border-radius:10px;color:#101944}
.st-key-shyam_records_table button{width:30px!important;min-width:30px!important;height:30px!important;min-height:30px!important}
.st-key-shyam_records_table [class*="receipt_draft_"] label[data-baseweb="checkbox"]{width:30px!important;height:30px!important;min-height:30px!important}
.st-key-save_invoice_receipt_batch button{background:linear-gradient(110deg,#08b61b,#008900)!important;color:white!important;border-radius:12px!important}
.sr-heading{display:flex;align-items:center;gap:16px;margin:10px 0 18px}.sr-icon{background:#e3edff;color:#0064ff;padding:15px;border-radius:16px;font-size:30px}.sr-heading h2{margin:0!important;padding:0!important;color:#0c1745}.sr-heading p{margin:4px 0;color:#34466d}.sr-total{margin-left:auto;border:1px solid #cbd9ff;border-radius:16px;padding:12px 24px;background:#eef3ff}.sr-total strong{display:block;font-size:24px;color:#0c1745}
.sr-board{border:1px solid #d4dfff;border-radius:18px;padding:16px;background:#ffffff99;margin:16px 0}.sr-board h3{font-size:22px;margin:0 0 12px;color:#101944}.sr-board small{font-size:14px;font-weight:400;margin-left:16px}.sr-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.sr-card{display:flex;align-items:center;gap:14px;border:1px solid #d2dfff;border-radius:15px;padding:14px;background:#eaf1ff}.sr-card:nth-child(2){background:#edfff0;border-color:#d2eed8}.sr-card:nth-child(3){background:#f3edff;border-color:#e5d7ff}.sr-card:nth-child(4){background:#fff0f2;border-color:#ffdce3}.sr-rank{font-size:22px;color:#0064ff;font-weight:800}.sr-card b{display:block}.sr-card em{margin-left:auto;text-align:right;font-style:normal}.sr-status{display:inline-block;border-radius:10px;padding:4px 9px;font-size:12px;font-weight:700;white-space:nowrap;background:#fff0cf;color:#a34c00}.sr-status.received{background:#ddf8df;color:#087822}
@media(max-width:800px){.sr-cards{grid-template-columns:repeat(2,1fr)}.sr-heading{flex-wrap:wrap}.sr-total{margin-left:0}.sr-card{padding:10px;gap:8px}.sr-card em{font-size:12px}}
</style>''', unsafe_allow_html=True)


def heading(revenue):
    st.markdown(f'<div class="sr-heading"><span class="sr-icon">▱</span><div><h2>Records</h2><p>View, filter and manage all trip records.</p></div><div class="sr-total">Total Revenue (All Branches)<strong>{format_inr(revenue)}</strong></div></div>', unsafe_allow_html=True)


def leaderboard(items, day):
    cards = ''.join(f'<div class="sr-card"><span class="sr-rank">{rank}</span><div><b>{escape(branch)}</b>{count} Trips</div><em><b>{format_inr(revenue)}</b>Total Revenue</em></div>' for rank,(branch,count,revenue) in enumerate(items,1) if branch != 'Total')
    st.markdown(f'<div class="sr-board"><h3>▥ &nbsp; Trip Leaderboard <small>{day:%B %Y}</small></h3><div class="sr-cards">{cards}</div></div>', unsafe_allow_html=True)
