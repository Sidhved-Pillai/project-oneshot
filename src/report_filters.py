"""Batch report controls without rerunning the app while filters are edited."""
import datetime as dt
import streamlit as st
import streamlit.components.v1 as components
from .operational_dates import OPERATIONS_START


def pnl_visibility_script():
    # Display only: the form still submits every value together and Python
    # enforces report permissions. Switching report type requires no server call.
    return '''<script>
(()=>{const doc=parent.document,form=doc.querySelector('.st-key-report_filters');
if(!form)return;parent.__oneshotReportFilters?.disconnect();
const update=()=>{const buttons=[...form.querySelectorAll('button')];
const active=buttons.find(b=>b.innerText.trim()==='P&L'&&(b.getAttribute('aria-pressed')==='true'||b.getAttribute('aria-selected')==='true'||b.dataset.testid?.endsWith('Active')));
const panel=form.querySelector('.st-key-report_pnl_filters');if(panel){const display=active?'':'none';if(panel.style.display!==display)panel.style.display=display}};
const observer=new MutationObserver(update);observer.observe(form,{subtree:true,childList:true,attributes:true,attributeFilter:['aria-pressed','aria-selected','data-testid']});
parent.__oneshotReportFilters=observer;update();})();
</script>'''


def render_report_filters(user, report_options, vehicles, today=None):
    today=today or dt.date.today()
    if st.session_state.get('report_type') not in (None,*report_options):
        st.session_state['report_type']='DTR'
    vehicle_options=['All',*vehicles]
    if st.session_state.get('pnl_vehicle_filter') not in (None,*vehicle_options):
        st.session_state['pnl_vehicle_filter']='All'
    with st.container(key='report_filters'),st.form('report_filter_form',border=False):
        c1,c2=st.columns(2)
        start=c1.date_input('Records from',value=today.replace(day=1),format='DD/MM/YYYY',key='report_from_v2',min_value=OPERATIONS_START)
        end=c2.date_input('Records to',value=today,format='DD/MM/YYYY',key='report_to_v2',min_value=OPERATIONS_START)
        kind=st.segmented_control('Report type',report_options,default='DTR',key='report_type') or 'DTR'
        ownership,vehicle='Both','All'
        if 'P&L' in report_options:
            with st.container(key='report_pnl_filters'):
                ownership=st.segmented_control('Own or outside vehicle',['Both','Own','Outside','Vehicle No. Wise'],default='Both',key='pnl_ownership_filter') or 'Both'
                vehicle=st.selectbox('Vehicle no.',vehicle_options,key='pnl_vehicle_filter')
        submitted=st.form_submit_button('Apply Filter',type='primary',key='apply_report_filters')
    if 'P&L' in report_options:
        components.html(pnl_visibility_script(),height=0)
    requested=st.session_state.pop('report_apply_requested',False)
    if submitted or requested:
        if start>end:
            st.error('Records to must be on or after Records from. Your previous report is still shown.')
        else:
            st.session_state['report_applied_filters']={
                'user':user,'start':start,'end':end,'kind':kind,
                'ownership':ownership if kind=='P&L' else 'Both',
                'vehicle':vehicle if kind=='P&L' else 'All',
            }
    applied=st.session_state.get('report_applied_filters')
    if not applied or applied.get('user')!=user or applied.get('kind') not in report_options:
        st.info('Choose your filters, then click Apply Filter to load the report.')
        return None,False
    return applied,bool((submitted or requested) and start<=end)
