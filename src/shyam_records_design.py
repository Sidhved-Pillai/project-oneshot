"""Presentation for Shyam's Records workspace; no persistence or filter logic."""
from html import escape
import streamlit as st
from .number_format import format_inr

def icon(path):
    return f'<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="{path}"/></svg>'

FOLDER = icon('M3 7V5h6l2 2h10v13H3z M3 10h18')
TRUCK = icon('M2 5h12v13H2z M14 10h4l4 4v4h-8 M5 18a2 2 0 1 0 4 0 M16 18a2 2 0 1 0 4 0')
CHART = icon('M4 20V10h3v10 M11 20V4h3v16 M18 20V8h3v12')


def styles():
    st.markdown('''<style>
.st-key-shyam_records{color:#101944}
.st-key-shyam_records [data-testid="stVerticalBlock"]{gap:.65rem}
.st-key-shyam_records_filters,.st-key-shyam_records_table{background:linear-gradient(120deg,#fff,#f5f8ff);border:1px solid #d4dfff!important;border-radius:18px!important;padding:16px!important;box-shadow:0 4px 14px #1555cc08}
.st-key-shyam_records label p{font-size:14px!important;color:#111b48}
.st-key-shyam_records [data-testid="stForm"]{border:0;padding:0}
.st-key-shyam_records [data-testid="stHorizontalBlock"]{gap:12px}
/* Rows remain white; only the explicitly keyed header is tinted. */
.st-key-shyam_records_table{padding:8px!important;background:#fff!important}
.st-key-shyam_records_table > div{min-width:1250px}
.st-key-shyam_records_table [data-testid="stHorizontalBlock"]{align-items:center;gap:8px!important;border-bottom:1px solid #e6eafb;padding:4px 0;background:transparent;border-radius:0}
.st-key-shyam_records_table [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"]{border:0;padding:0;gap:8px!important;min-width:0}
.st-key-shyam_records_header{background:#e9edfc;border-radius:10px 10px 0 0;padding:4px 0}
.st-key-shyam_records_table p{font-size:12px!important;line-height:1.4!important;overflow-wrap:break-word;margin:0!important;color:#101944}
.st-key-shyam_records_table [class*="st-key-view_record_"] button,
.st-key-shyam_records_table [class*="st-key-delete_record_"] button{width:30px!important;min-width:30px!important;height:28px!important;min-height:28px!important;border-radius:9px!important;box-shadow:none!important;padding:0!important}
.st-key-shyam_records_table [class*="st-key-view_record_"] button{border:1px solid #d4dfff!important;background:#f8faff!important;color:#142052!important}
.st-key-shyam_records_table [class*="st-key-delete_record_"] button{border:1px solid #ffcbd1!important;background:#fff0f2!important;color:#ed1731!important}
.st-key-shyam_records_table [class*="st-key-delete_record_"] button p{display:none!important}
.st-key-shyam_records_table [class*="receipt_draft_"]{min-width:28px!important;width:28px!important}
.st-key-shyam_records_table [class*="receipt_draft_"] label[data-baseweb="checkbox"]{width:28px!important;height:28px!important;min-height:28px!important}
.st-key-shyam_records_table [class*="receipt_draft_"] label p{font-size:22px!important;color:#0da64c!important}
.st-key-shyam_records_table [class*="receipt_draft_"] label:has(input:checked) p{color:white!important}
.st-key-shyam_records_filters button[kind="primaryFormSubmit"]{background:linear-gradient(110deg,#1685ff,#0051ff)!important;color:white!important;border:0!important;border-radius:10px!important}
.sr-filter-title{font-size:20px;font-weight:750;color:#101944;margin-bottom:12px}
.st-key-shyam_records_filters [data-testid="stFormSubmitButton"]{padding-top:22px}
.st-key-shyam_records_filters [data-testid="stFormSubmitButton"] button{height:38px!important;min-height:38px!important;white-space:nowrap}
.st-key-save_invoice_receipt_batch button{background:linear-gradient(110deg,#08b61b,#008900)!important;color:white!important;border-radius:12px!important}
.sr-heading{display:flex;align-items:center;gap:16px;margin:0 0 12px}.sr-icon{background:#e3edff;color:#0064ff;padding:12px;border-radius:16px;font-size:30px}.sr-heading h2{margin:0!important;padding:0!important;color:#0c1745}.sr-heading p{margin:4px 0;color:#34466d}.sr-total{margin-left:auto;border:1px solid #cbd9ff;border-radius:16px;padding:12px 24px;background:#eef3ff}.sr-total strong{display:block;font-size:24px;color:#0c1745}
.sr-board{border:1px solid #d4dfff;border-radius:18px;padding:16px;background:#ffffff99;margin:16px 0}.sr-board h3{font-size:22px;margin:0 0 12px;color:#101944}.sr-board small{font-size:14px;font-weight:400;margin-left:16px}.sr-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.sr-card{display:flex;align-items:center;gap:14px;border:1px solid #d2dfff;border-radius:15px;padding:14px;background:#eaf1ff}.sr-card:nth-child(2){background:#edfff0;border-color:#d2eed8}.sr-card:nth-child(3){background:#f3edff;border-color:#e5d7ff}.sr-card:nth-child(4){background:#fff0f2;border-color:#ffdce3}.sr-rank{font-size:22px;color:#0064ff;font-weight:800}.sr-card b{display:block}.sr-truck{color:#0064ff;display:flex}.sr-rank{background:#dceaff;border-radius:8px;padding:2px 7px}.sr-card:nth-child(2) .sr-truck,.sr-card:nth-child(2) .sr-rank{color:#008c1b}.sr-card:nth-child(3) .sr-truck,.sr-card:nth-child(3) .sr-rank{color:#6b24e8}.sr-card:nth-child(4) .sr-truck,.sr-card:nth-child(4) .sr-rank{color:#ed233a}.sr-card em{margin-left:auto;text-align:right;font-style:normal}.sr-status{display:inline-block;border-radius:10px;padding:4px 9px;font-size:12px;font-weight:700;white-space:nowrap;background:#fff0cf;color:#a34c00}.sr-status.received{background:#ddf8df;color:#087822}
@media(max-width:800px){.sr-cards{grid-template-columns:repeat(2,1fr)}.sr-heading{flex-wrap:wrap}.sr-total{margin-left:0}.sr-card{padding:10px;gap:8px}.sr-card em{font-size:12px}}
.st-key-shyam_records h2{font-size:30px!important}.sr-heading p{font-size:14px}.sr-board h3{display:flex;align-items:center}.sr-card{font-size:13px;padding:12px}.sr-total{font-size:12px}.sr-total strong{font-size:22px}.st-key-shyam_records_table [data-testid="stVerticalBlock"]{gap:0!important}
.sr-table-title{font-size:20px;font-weight:750;display:flex;align-items:center;gap:12px}.sr-table-title small{font-size:12px;font-weight:400}.st-key-shyam_records [data-testid="stSubheader"]{color:#101944}.st-key-shyam_records_table [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]){min-height:38px}
/* Keep the reference's compact table geometry independent of global widget styles. */
.st-key-shyam_records [data-testid="stElementContainer"]{margin-bottom:0!important}
.st-key-shyam_records_filters [data-baseweb="input"],
.st-key-shyam_records_filters [data-baseweb="select"]>div{min-height:36px!important;border-radius:10px!important}
.st-key-shyam_records_filters input{font-size:13px!important;min-height:34px!important;padding-top:5px!important;padding-bottom:5px!important}
.st-key-shyam_records_filters [data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"],
.st-key-shyam_records_filters [data-testid="stFormSubmitButton"] button[kind="primary"]{background:linear-gradient(110deg,#1685ff,#0051ff)!important;color:#fff!important}
.st-key-shyam_records_table [class*="st-key-shyam_record_row_"]{background:#fff!important;border-radius:0!important;padding:0!important;border:0!important;box-shadow:none!important}
.st-key-shyam_records_table [class*="st-key-shyam_record_row_"]>[data-testid="stVerticalBlock"]{gap:0!important}
.st-key-shyam_records_table [class*="st-key-shyam_record_row_"] [data-testid="stHorizontalBlock"]{background:#fff!important;border-radius:0!important;min-height:36px!important;padding:2px 0!important}
.st-key-shyam_records_table [class*="st-key-shyam_record_row_"] [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"]{border-bottom:0!important;padding:0!important;min-height:30px!important;gap:6px!important}
.st-key-shyam_records_table [data-testid="stColumn"]{min-width:0!important;overflow:visible!important}
.st-key-shyam_records_table [data-testid="stColumn"] [data-testid="stMarkdownContainer"] p{font-size:12px!important;line-height:1.3!important}
.st-key-shyam_records_table [class*="st-key-view_record_"] button span{color:#142052!important;font-size:19px!important}
.st-key-shyam_records_table [class*="st-key-delete_record_"] button span{color:#ed1731!important;font-size:19px!important}
.st-key-shyam_records_table [class*="st-key-delete_record_"] button:disabled span{color:#ed1731!important}
.st-key-shyam_records_table [class*="receipt_draft_"] label[data-baseweb="checkbox"]{min-width:28px!important;margin:0!important;padding:0!important;border-width:1.5px!important}
.st-key-shyam_records_table [class*="receipt_draft_"] label [data-testid="stMarkdownContainer"] p{font-size:19px!important;line-height:1!important}
.st-key-shyam_records_header{background:#e9edfc!important;min-height:34px!important;padding:4px 0!important}
.st-key-shyam_records_header [data-testid="stHorizontalBlock"]{border:0!important;background:#e9edfc!important;min-height:28px!important}
.sr-board{padding:12px!important;margin:8px 0!important}.sr-board h3{font-size:20px!important;margin-bottom:10px!important}
.sr-card{padding:10px!important;gap:10px!important;min-height:64px;box-sizing:border-box}
.sr-card em{border-left:1px solid #d5def2;padding-left:12px}.sr-card:nth-child(2) .sr-rank{background:#d5f7db}.sr-card:nth-child(3) .sr-rank{background:#eadbff}.sr-card:nth-child(4) .sr-rank{background:#ffe0e6}
.st-key-shyam_records_prev button,.st-key-shyam_records_next button{width:30px!important;min-width:30px!important;height:30px!important;min-height:30px!important;border-radius:9px!important;padding:0!important;box-shadow:none!important}
.st-key-shyam_records_table{scrollbar-width:auto;scrollbar-color:#3174ed #edf2ff}

</style>''', unsafe_allow_html=True)


def heading(revenue):
    st.markdown(f'<div class="sr-heading"><span class="sr-icon">{FOLDER}</span><div><h2>Records</h2><p>View, filter and manage all trip records.</p></div><div class="sr-total">Total Revenue (All Branches)<strong>{format_inr(revenue)}</strong></div></div>', unsafe_allow_html=True)


def leaderboard(items, day):
    cards = ''.join(f'<div class="sr-card"><span class="sr-rank">{rank}</span><span class="sr-truck">{TRUCK}</span><div><b>{escape(branch)}</b>{count} Trips</div><em><b>{format_inr(revenue)}</b>Total Revenue</em></div>' for rank,(branch,count,revenue) in enumerate(items,1) if branch != 'Total')
    st.markdown(f'<div class="sr-board"><h3>{CHART} &nbsp; Trip Leaderboard <small>{day:%B %Y}</small></h3><div class="sr-cards">{cards}</div></div>', unsafe_allow_html=True)
