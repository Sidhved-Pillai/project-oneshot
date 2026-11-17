"""Exercise the production report renderer without login/network setup."""
import ast
import datetime as dt
from pathlib import Path
from streamlit.testing.v1 import AppTest
from tests.test_report_filters import run


def report_source(db_path):
    tree=ast.parse(Path('app.py').read_text())
    modules={'src.expense_linking','src.invoice_display','src.number_format','src.expense_periods',
        'src.trip_dtr_report_v3','src.rtgs_report_v3','src.text_normalization_v2','src.transporter_profiles',
        'src.vehicle_normalization','src.vehicle_placer','src.current_pnl_report_v6','src.report_filters_v3','src.report_design',
        'src.billtee_payments','src.upi_payments','src.balance_reconciliation','src.balance_payments',
        'src.report_scroll','src.dtr_dates','src.ashok_dates','src.vijay_finance'}
    helpers={'scope_report_rows','clean_text','number','as_date','unpack','ownership_matches','request_label',
        'rtgs_row_styles','rtgs_remark','trip_auto_remark','dtr_cell_value','changed_dtr_rows',
        'cached_report_dtr_frame','cached_dtr_excel','cached_rtgs_excel','cached_pnl_excel','render_generate_reports'}
    nodes=[n for n in tree.body if isinstance(n,ast.ImportFrom) and n.module in modules or isinstance(n,ast.FunctionDef) and n.name in helpers]
    prefix='''
import datetime as dt
from contextlib import nullcontext
import hashlib,json,re
from numbers import Number
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from src import current_pnl_report_v6 as pnl_reporting
from src.request_store import RequestStore
from tests.test_pending_payments import trip
from src.operational_dates import OPERATIONS_START
current_user='Sid'
can_generate_reports=can_generate_pnl=True
KNOWN_COMPANIES=[]
KNOWN_LOCATIONS=[]
page_intro=lambda *args:None
workflow_steps=lambda *args:None
audit_action=lambda *args:None
complete_rtgs_download=lambda *args:None
'''
    setup=f'''
store=RequestStore({'sqlite:///'+str(db_path)!r})
original_read=store.dashboard_snapshot
def counted_read(*args,**kwargs):
    st.session_state['snapshot_reads']=st.session_state.get('snapshot_reads',0)+1
    return original_read(*args,**kwargs)
store.dashboard_snapshot=counted_read
if 'fixture' not in st.session_state:
    trip(store,trip_date=dt.date(2026,11,10),invoice_number='TEST-INV',revenue=3000,rtgs_advance=1000)
    st.session_state['_report_source']=store.dashboard_snapshot()[:3]
    st.session_state['_report_refresh_metadata']=True
    st.session_state['fixture']=True
render_generate_reports()
'''
    return prefix+ast.unparse(ast.Module(body=nodes,type_ignores=[]))+setup


def apply(app,kind):
    app.get('button_group')[0].set_value([kind])
    app.button(key='apply_report_filters').click()
    run(app)
    assert not app.exception


def test_all_report_formats_keep_working_and_apply_refreshes_saved_entries(tmp_path):
    path=tmp_path/'reports.db'
    app=AppTest.from_string(report_source(path)).run()
    assert not app.exception and not app.dataframe
    apply(app,'DTR')
    assert len(app.dataframe[0].value)==1
    assert app.dataframe[0].value.iloc[0]['Invoice No.']=='TEST-INV'
    reads=app.session_state['snapshot_reads']
    app.date_input(key='report_to_v2').set_value(dt.date(2026,11,16))
    run(app)
    assert app.session_state['snapshot_reads']==reads
    assert len(app.dataframe[0].value)==1
    from src.request_store import RequestStore
    from tests.test_pending_payments import trip
    trip(RequestStore('sqlite:///'+str(path)),trip_date=dt.date(2026,11,11),invoice_number='SECOND')
    apply(app,'DTR')
    assert len(app.dataframe[0].value)==2
    apply(app,'RTGS')
    assert len(app.dataframe[0].value)==1
    assert app.dataframe[0].value.iloc[0]['Amount']==1000
    assert app.dataframe[0].value.iloc[0]['Invoice No.']=='TEST-INV'
    assert app.dataframe[0].value.iloc[0]['Account Number']=='001234'
    from src.rtgs_report_v3 import RTGS_REVIEW_COLUMNS
    assert app.dataframe[1].value.columns.tolist()==RTGS_REVIEW_COLUMNS
    assert 'Branch' not in app.dataframe[1].value.columns
    assert app.dataframe[1].value.iloc[0]['BENE_ACC_NO']=='001234'
    reads=app.session_state['snapshot_reads']
    app.checkbox(key='rtgs_select_all').check()
    run(app)
    assert not app.exception and app.session_state['snapshot_reads']==reads
    apply(app,'P&L')
    assert 'Profit' in app.dataframe[0].value.columns


def test_rtgs_download_requests_a_fresh_fragment_snapshot():
    from types import SimpleNamespace
    tree=ast.parse(Path('app.py').read_text())
    callback=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='complete_rtgs_download')
    calls=[];state={}
    namespace={'store':SimpleNamespace(mark_rtgs_done=lambda numbers,edited_by:calls.append((numbers,edited_by)) or len(numbers)),
        'st':SimpleNamespace(session_state=state),'current_user':'Nikhat','audit_action':lambda *args:None}
    exec(compile(ast.Module(body=[callback],type_ignores=[]),'callback','exec'),namespace)
    namespace['complete_rtgs_download'](['REQ-1'],dt.date(2026,11,1),dt.date(2026,11,17))
    assert calls==[(['REQ-1'],'Nikhat')] and state['_report_refresh_source'] is True


def test_report_switches_render_immediately_without_reapplying_dates(tmp_path):
    app=AppTest.from_string(report_source(tmp_path/'switch.db')).run()
    app.date_input(key='report_from_v2').set_value(dt.date(2026,11,10))
    app.date_input(key='report_to_v2').set_value(dt.date(2026,11,10))
    apply(app,'DTR')
    for kind,column in [('RTGS','Amount'),('P&L','Profit'),('DTR','Invoice No.')]:
        app.get('button_group')[0].set_value([kind]);run(app)
        assert not app.exception
        assert column in app.dataframe[0].value.columns
        assert app.session_state['report_applied_filters']['start']==dt.date(2026,11,10)
        assert app.session_state['report_applied_filters']['end']==dt.date(2026,11,10)
    app.date_input(key='report_from_v2').set_value(dt.date(2026,11,11))
    app.date_input(key='report_to_v2').set_value(dt.date(2026,11,12))
    apply(app,'DTR')
    app.get('button_group')[0].set_value(['RTGS']);run(app)
    assert not app.exception
    assert app.dataframe[0].value.empty
