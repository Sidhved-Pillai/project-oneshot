"""Presentation for report studio; never transforms report or export data."""
import streamlit as st
from .number_format import format_inr


def report_styles(kind):
    if kind == 'P&L':
        return
    st.markdown('''<style>
    .st-key-report_type [data-testid="stButtonGroup"] {gap:8px;flex-wrap:wrap}
    .st-key-report_type button {border:1px solid #dce5ff!important;border-radius:16px!important;
      padding:12px 28px!important;min-width:180px;min-height:52px;box-shadow:0 3px 7px #154fff14;
      color:#0b1646!important;font-weight:750!important;background:#ffffff!important}
    .st-key-report_type button[kind="segmented_controlActive"] {
      color:white!important;background:linear-gradient(110deg,#329cff,#0055ff)!important;border-color:#88c6ff!important}
    .st-key-report_filters {background:linear-gradient(120deg,#fff,#f5f8ff);
      padding:18px 22px;border:1px solid #dce6ff;border-radius:20px;box-shadow:0 3px 9px #0055ff0d;margin:6px 0 18px}
    .st-key-report_filters label {color:#0b1646;font-weight:650}
    .st-key-report_filters button {border-radius:14px!important;background:linear-gradient(110deg,#268cff,#0055ff)!important;border-color:#70a7ff!important;color:white!important}
    .st-key-report_type [data-testid="stWidgetLabel"] {display:none}
    .st-key-report_results {padding:22px 18px;border:1px solid #dce6ff;border-radius:20px;
      background:linear-gradient(120deg,#fff,#f9fbff);box-shadow:0 3px 10px #0055ff0c}
    .st-key-report_results h3 {font-size:25px!important;color:#0b1646!important;padding:0!important;margin:0!important}
    .st-key-report_results [data-testid="stCaptionContainer"] {color:#425380}
    .st-key-report_results [data-testid="stDataFrame"] {border-radius:14px;border:1px solid #e0e7fa;
      overflow:hidden;box-shadow:0 2px 6px #174cff09}
    .st-key-report_download button {border-radius:15px!important;background:white!important;
      color:#0b1646!important;border:1px solid #d8e3ff!important;box-shadow:0 2px 6px #0055ff15}
    .st-key-report_download_rtgs button {background:linear-gradient(110deg,#14bd2a,#00880e)!important;
      border:1px solid #12a324!important;color:white!important;border-radius:15px!important}
    .report-summary {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;
      border:1px solid #e0e7fa;border-radius:16px;padding:18px;background:#fbfdff;margin-top:14px}
    .report-summary>div {border-right:1px solid #dce4fa;padding:0 18px;color:#0b1646;font-size:14px}
    .report-summary>div:last-child {border:0;background:#eaf2ff;border-radius:12px}
    .report-summary strong {display:block;font-size:25px;margin-top:5px;color:#0b1646}
    .report-summary>div:last-child strong {color:#0055ff}
    @media(max-width:700px){
      .st-key-report_type button {min-width:0;padding:9px 14px!important;min-height:44px}
      .st-key-report_filters,.st-key-report_results {padding:14px 10px;border-radius:16px}
      .report-summary {grid-template-columns:repeat(2,minmax(0,1fr));padding:12px;gap:16px}
      .report-summary>div {padding:0 6px;border:0}.report-summary strong {font-size:21px}
    }
    </style>''',unsafe_allow_html=True)


def rtgs_summary(rows):
    done=sum(bool(row.get('rtgs_done')) for row in rows)
    total=sum(float(row.get('rtgs_advance') or 0) for row in rows)
    st.markdown('<div class="report-summary">'+''.join(
        f'<div>{label}<strong>{value}</strong></div>' for label,value in [
            ('Total Records',len(rows)),('RTGS Done',done),('Pending',len(rows)-done),
            ('Total Amount',format_inr(total))])+ '</div>',unsafe_allow_html=True)
