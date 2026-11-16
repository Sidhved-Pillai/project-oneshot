import datetime as dt
import ast
from pathlib import Path
from streamlit.testing.v1 import AppTest


def filter_app(user='Sid',options=None):
    return AppTest.from_string('''
import streamlit as st
import datetime as dt
from src.report_filters import render_report_filters
filters,submitted=render_report_filters('''+repr(user)+','+repr(options or ['DTR','RTGS','P&L'])+''',['MH01TEST','MH02TEST'],dt.date(2026,11,17))
if submitted:st.session_state['loads']=st.session_state.get('loads',0)+1
if filters:st.json({k:str(v) for k,v in filters.items()})
''').run()


def run(app):
    # Streamlit 1.50's AppTest models segmented controls as multi-selects.
    # Supply the same single-index list sent by the real browser.
    for group in app.get('button_group'):
        if group._value is None:
            group.set_value([app.session_state[group.key]])
    return app.run()


def test_dates_type_and_pnl_filters_apply_together():
    app=filter_app();assert not app.exception
    assert not app.json
    app.date_input(key='report_from_v2').set_value(dt.date(2026,10,1))
    app.date_input(key='report_to_v2').set_value(dt.date(2026,10,31))
    app.get('button_group')[0].set_value(['P&L'])
    app.get('button_group')[1].set_value(['Vehicle No. Wise'])
    app.selectbox(key='pnl_vehicle_filter').select('MH02TEST')
    app.button(key='apply_report_filters').click();run(app)
    assert not app.exception
    applied=app.session_state['report_applied_filters']
    assert (applied['start'],applied['end'],applied['kind'],applied['ownership'],applied['vehicle'])==(dt.date(2026,10,1),dt.date(2026,10,31),'P&L','Vehicle No. Wise','MH02TEST')
    assert app.session_state['loads']==1
    app.date_input(key='report_from_v2').set_value(dt.date(2026,11,1));run(app)
    assert app.session_state['report_applied_filters']==applied
    assert app.session_state['loads']==1


def test_invalid_range_keeps_last_report_and_ashok_is_dtr_only():
    app=filter_app('Ashok',['DTR'])
    app.button(key='apply_report_filters').click();run(app)
    saved=app.session_state['report_applied_filters'].copy()
    app.date_input(key='report_from_v2').set_value(dt.date(2026,12,1))
    app.button(key='apply_report_filters').click();run(app)
    assert app.error and app.session_state['report_applied_filters']==saved
    assert not app.selectbox
    assert [o.content for o in app.get('button_group')[0].options]==['DTR']


def test_dashboard_jump_applies_requested_pnl_and_refresh_is_fragment_only():
    app=filter_app()
    app.session_state['report_type']='P&L'
    app.session_state['report_apply_requested']=True
    run(app)
    assert app.session_state['report_applied_filters']['kind']=='P&L'
    tree=ast.parse(Path('app.py').read_text())
    renderer=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render_generate_reports')
    assert any(isinstance(d,ast.Attribute) and d.attr=='fragment' for d in renderer.decorator_list)
