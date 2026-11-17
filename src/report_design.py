"""Scoped report-studio presentation. Export formats are managed separately."""
import streamlit as st
from .number_format import format_inr

ICONS={
'bars':'<path d="M4 20V12h4v8m3 0V7h4v13m3 0V3h4v17"/>',
'layers':'<path d="m12 3 10 6-10 6L2 9zm-10 9 10 6 10-6M2 16l10 6 10-6"/>',
'send':'<path d="m22 2-7 20-4-9-9-4 20-7ZM11 13 22 2"/>',
'clock':'<circle cx="12" cy="12" r="9"/><path d="M12 6v6l5 3"/>',
'wallet':'<rect x="3" y="5" width="18" height="15" rx="2"/><path d="M3 8h18m-5 4h5v5h-5zM6 5V2h13v3"/>',
}
def icon(name):
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>'


def report_heading():
    st.markdown(f'<div class="report-heading"><span>{icon("bars")}</span><div><h2>Generate Reports</h2><p>Create DTR, RTGS, or P&amp;L reports based on your entries.</p></div></div>',unsafe_allow_html=True)


def report_styles(kind):
    if kind=='P&L':return
    st.markdown('''<style>
    .st-key-report_studio {width:calc(100% + 7vw)!important;max-width:calc(100vw - 40px)!important;margin-left:-3.5vw!important;color:#080f42;gap:14px!important}
    .st-key-report_studio [data-testid="stVerticalBlock"] {gap:12px}
    .report-heading {display:flex;gap:20px;align-items:center;margin:6px 2px 10px;color:#080f42}
    .report-heading>span {width:62px;height:62px;border-radius:17px;background:linear-gradient(135deg,#d4e4ff,#eaf2ff);display:grid;place-items:center;color:#005bff}
    .report-heading svg {width:35px;height:35px}
    .report-heading h2 {font-size:30px!important;font-weight:800!important;margin:0!important;padding:0!important;color:#080f42!important;line-height:1.25!important}
    .report-heading p {font-size:16px;color:#263978;margin:4px 0 0}
    .st-key-report_studio .st-key-report_type [data-testid="stWidgetLabel"] {display:none}
    .st-key-report_studio .st-key-report_type [role="group"] {gap:6px!important}
    .st-key-report_studio .st-key-report_type button {border:1px solid #dce5ff!important;border-radius:15px!important;
      padding:10px 26px!important;min-width:200px;min-height:50px!important;box-shadow:0 3px 5px #154fff18;
      color:#080f42!important;background:#ffffff!important;font-weight:750!important}
    .st-key-report_studio .st-key-report_type button p {font-weight:750!important;font-size:17px!important;white-space:nowrap}
    .st-key-report_studio .st-key-report_type button[kind="segmented_controlActive"] {color:white!important;background:linear-gradient(110deg,#329cff,#0065ff)!important;border:2px solid white!important;box-shadow:0 2px 6px #0055ff60}
    .st-key-report_filters {background:linear-gradient(115deg,#fff,#f5f7ff);padding:14px 20px!important;border:1px solid #dce6ff;border-radius:18px;box-shadow:0 3px 7px #0055ff13;margin:2px 0 4px}
    .st-key-report_studio .st-key-report_filters [data-testid="stHorizontalBlock"] {gap:16px!important;flex-wrap:nowrap!important}
    .st-key-report_studio .st-key-report_filters [data-testid="stColumn"] {min-width:0!important}
    .st-key-report_studio .st-key-report_type [data-testid="stIconMaterial"] {font-size:24px!important}
    .st-key-report_studio label p {font-size:14px!important;font-weight:650!important;color:#080f42!important}
    .st-key-report_studio input {font-size:14px!important;color:#10183f!important;min-height:36px!important;padding:7px 11px!important;background:white!important}
    .st-key-report_studio [data-baseweb="input"],.st-key-report_studio [data-baseweb="select"]>div {background:white!important;border:1px solid #d5e0ff!important;border-radius:12px!important;min-height:40px!important;box-shadow:0 2px 5px #0055ff0d}
    .st-key-report_studio [data-baseweb="select"] {font-size:14px!important}
    .st-key-report_studio [data-baseweb="select"] input {min-height:0!important;padding:0!important}
    .st-key-report_studio .st-key-report_filters button {border-radius:14px!important;background:linear-gradient(110deg,#268cff,#0055ff)!important;border:1px solid #70a7ff!important;color:white!important;min-height:42px!important;padding:8px 13px!important;white-space:nowrap}
    .st-key-report_studio .st-key-report_filters button p {font-size:15px!important;font-weight:650!important}
    .st-key-report_results {padding:17px 16px 20px!important;border:1px solid #dce6ff;border-radius:18px;background:linear-gradient(120deg,#fff,#fafcff);box-shadow:0 3px 9px #0055ff10}
    .st-key-report_results h3 {font-size:25px!important;font-weight:800!important;color:#080f42!important;padding:0!important;margin:0!important;line-height:1.15!important}
    .st-key-report_results [data-testid="stCaptionContainer"] p {font-size:14px!important;color:#33437a!important;margin:0!important}
    .st-key-report_results [data-testid="stDataFrame"] {border-radius:13px;border:1px solid #dce4fb;overflow:hidden;box-shadow:0 2px 5px #174cff0d}
    .st-key-report_studio .st-key-report_download button {border-radius:14px!important;background:white!important;color:#080f42!important;border:1px solid #d8e3ff!important;box-shadow:0 2px 5px #0055ff20;padding:9px 16px!important;min-height:42px!important}
    .st-key-report_studio .st-key-report_download_rtgs button {background:linear-gradient(110deg,#18c52c,#008b0a)!important;border:1px solid #12a324!important;color:white!important;border-radius:14px!important;padding:9px 18px!important;min-height:42px!important}
    .st-key-report_studio .st-key-report_download button p,.st-key-report_studio .st-key-report_download_rtgs button p {font-size:15px!important;font-weight:700!important;white-space:nowrap}
    .st-key-report_tools {padding:0 0 2px}
    .st-key-report_tools label p {font-size:13px!important}
    .st-key-report_studio .st-key-report_actions button {min-height:35px!important;padding:5px 14px!important;font-size:13px!important;border-radius:10px!important}
    .st-key-report_studio .st-key-report_actions button p {font-size:13px!important}
    .report-summary {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid #e0e7fa;border-radius:15px;padding:12px;background:#fbfdff;margin-top:4px;box-shadow:0 2px 6px #174cff0b}
    .report-summary>div {display:flex;align-items:center;gap:18px;border-right:1px solid #cbd9ff;padding:0 18px;color:#080f42;font-size:14px;font-weight:650}
    .report-summary .summary-icon {width:52px;height:52px;display:grid;place-items:center;background:#e7f9e8;border-radius:16px;color:#00a10d;flex-shrink:0}
    .report-summary svg {width:30px;height:30px}
    .report-summary>div:nth-child(3) .summary-icon {background:#fff2df;color:#ce7800}
    .report-summary>div:last-child {border:0;background:#e8f0ff;border-radius:12px;color:#0055ff}
    .report-summary>div:last-child .summary-icon {background:#e3edff;color:#0055ff}
    .report-summary strong {display:block;font-size:27px;line-height:1.25;margin-top:2px;font-weight:800}
    @media(max-width:900px){
      .st-key-report_studio {width:100%!important;max-width:100%!important;margin-left:0!important}
      .st-key-report_studio .st-key-report_type button {min-width:0;padding:8px 15px!important}
      .st-key-report_studio .st-key-report_type button p {font-size:14px!important}
      .st-key-report_studio .st-key-report_filters [data-testid="stHorizontalBlock"] {flex-wrap:wrap!important;gap:12px!important}
      .st-key-report_filters [data-testid="stColumn"] {min-width:180px!important;flex:1 1 180px!important}
      .report-summary {grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
      .report-summary>div {padding:6px;border:0;gap:8px}.report-summary strong {font-size:22px}
    }
    @media(max-width:550px){.report-heading h2{font-size:24px!important}.report-heading p{font-size:13px}.report-heading{gap:12px}.report-heading>span{width:48px;height:48px}
      .st-key-report_filters,.st-key-report_results {padding:12px 10px!important}
      .report-summary .summary-icon {width:33px;height:36px}.report-summary svg {width:23px}.report-summary>div{font-size:12px}.report-summary strong{font-size:19px}}
    </style>''',unsafe_allow_html=True)


def rtgs_summary(rows):
    done=sum(bool(row.get('rtgs_done')) for row in rows)
    total=sum(float(row.get('rtgs_advance') or 0) for row in rows)
    st.markdown('<div class="report-summary">'+''.join(
        f'<div><span class="summary-icon">{icon(symbol)}</span><div>{label}<strong>{value}</strong></div></div>' for symbol,label,value in [
            ('layers','Total Records',len(rows)),('send','RTGS Done',done),('clock','Pending',len(rows)-done),('wallet','Total Amount',format_inr(total))])+ '</div>',unsafe_allow_html=True)
