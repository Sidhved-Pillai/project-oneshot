"""Shared applied report dates, with separately batched P&L filters."""
import datetime as dt
import streamlit as st
import streamlit.components.v1 as components
from .operational_dates import OPERATIONS_START


def render_report_filters(user, report_options, vehicles, today=None):
    today=today or dt.date.today()
    if st.session_state.get('report_type') not in (None,*report_options):
        st.session_state['report_type']='DTR'
    kind=st.segmented_control('Report type',report_options,default='DTR',key='report_type',format_func=lambda value: {'DTR':'🚚  DTR Report','RTGS':'₹  RTGS Report','P&L':'↗  P&L Report'}[value]) or 'DTR'
    # Retire the previous client-only visibility observer on hot deployment.
    components.html('<script>parent.__oneshotReportFilters?.disconnect();</script>',height=0)
    requested=st.session_state.pop('report_apply_requested',False)
    applied=st.session_state.get('report_applied_filters')
    if applied and (applied.get('user')!=user or applied.get('kind') not in report_options):
        applied=None
    pnl=st.session_state.get('report_applied_pnl',{})
    if pnl.get('user')!=user:
        pnl={'user':user,'ownership':'Both','vehicle':'All'}
    vehicle_options=['All',*vehicles]
    if pnl['vehicle'] not in vehicle_options:
        pnl={**pnl,'vehicle':'All'}
    if applied and applied['kind']!=kind and not requested:
        # A format switch reuses only committed dates and P&L choices.
        st.session_state['report_from_v2']=applied['start']
        st.session_state['report_to_v2']=applied['end']
        applied={**applied,'kind':kind,
            'ownership':pnl['ownership'] if kind=='P&L' else 'Both',
            'vehicle':pnl['vehicle'] if kind=='P&L' else 'All'}
        st.session_state['report_applied_filters']=applied
    if kind=='P&L':
        if 'pnl_ownership_filter' not in st.session_state:
            st.session_state['pnl_ownership_filter']=pnl['ownership']
        if st.session_state.get('pnl_vehicle_filter') not in (None,*vehicle_options):
            st.session_state['pnl_vehicle_filter']='All'
        elif 'pnl_vehicle_filter' not in st.session_state:
            st.session_state['pnl_vehicle_filter']=pnl['vehicle']
    st.session_state.setdefault('report_from_v2',today.replace(day=1))
    st.session_state.setdefault('report_to_v2',today)
    with st.container(key='report_filters'),st.form('report_filter_form',border=False):
        if kind == 'P&L':
            c1,c2=st.columns(2)
            apply_column=None
        else:
            c1,c2,apply_column=st.columns([2,2,1],vertical_alignment='bottom')
        start=c1.date_input('Records from',value=None,format='DD/MM/YYYY',key='report_from_v2',min_value=OPERATIONS_START)
        end=c2.date_input('Records to',value=None,format='DD/MM/YYYY',key='report_to_v2',min_value=OPERATIONS_START)
        ownership,vehicle='Both','All'
        if kind=='P&L':
            with st.container(key='report_pnl_filters'):
                ownership=st.segmented_control('Own or outside vehicle',['Both','Own','Outside','Vehicle No. Wise'],default='Both',key='pnl_ownership_filter') or 'Both'
                vehicle=st.selectbox('Vehicle no.',vehicle_options,key='pnl_vehicle_filter')
        if apply_column is None:
            submitted=st.form_submit_button('Apply Filter',type='primary',key='apply_report_filters')
        else:
            with apply_column:
                submitted=st.form_submit_button('Apply Filter',type='primary',key='apply_report_filters',use_container_width=True)
    if submitted or requested:
        if start>end:
            st.error('Records to must be on or after Records from. Your previous report is still shown.')
        else:
            applied={'user':user,'start':start,'end':end,'kind':kind,
                'ownership':ownership,'vehicle':vehicle}
            st.session_state['report_applied_filters']=applied
            if kind=='P&L':
                st.session_state['report_applied_pnl']={'user':user,'ownership':ownership,'vehicle':vehicle}
    if not applied:
        st.info('Choose your filters, then click Apply Filter to load the report.')
        return None,False
    return applied,bool((submitted or requested) and start<=end)
