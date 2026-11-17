"""Applied report filters: shared dates and separately remembered format choices."""
import datetime as dt
import streamlit as st
from .operational_dates import OPERATIONS_START


def _options(rows, field):
    return ['All',*sorted({str(r.get(field) or '').strip() for r in rows}-{''},key=str.casefold)]


def render_report_filters(user, report_options, vehicles, today=None, rows=()):
    today=today or dt.date.today()
    if st.session_state.get('report_type') not in (None,*report_options):
        st.session_state['report_type']='DTR'
    kind=st.segmented_control('Report type',report_options,default='DTR',key='report_type',
        format_func=lambda value: {'DTR':':material/local_shipping: DTR Report','RTGS':':material/currency_rupee: RTGS Report','P&L':':material/trending_up: P&L Report'}[value]) or 'DTR'
    requested=st.session_state.pop('report_apply_requested',False)
    applied=st.session_state.get('report_applied_filters')
    if applied and (applied.get('user')!=user or applied.get('kind') not in report_options):
        applied=None
    pnl=st.session_state.get('report_applied_pnl',{})
    if pnl.get('user')!=user:
        pnl={'user':user,'ownership':'Both','vehicle':'All'}
    vehicle_options=['All',*vehicles]
    if pnl['vehicle'] not in vehicle_options:pnl={**pnl,'vehicle':'All'}
    details=st.session_state.get('report_applied_details',{})
    if details.get('user')!=user:details={'user':user}
    choices=details.get(kind,{})
    switched=bool(applied and applied['kind']!=kind)
    if switched and not requested:
        applied={**applied,'kind':kind,'details':choices,
            'ownership':pnl['ownership'] if kind=='P&L' else 'Both',
            'vehicle':pnl['vehicle'] if kind=='P&L' else 'All'}
        st.session_state['report_applied_filters']=applied
        st.session_state['report_from_v2']=applied['start']
        st.session_state['report_to_v2']=applied['end']
    if not applied and not requested:
        applied={'user':user,'kind':kind,'start':today.replace(day=1),'end':today,
            'ownership':'Both','vehicle':'All','details':{}}
        st.session_state['report_applied_filters']=applied
    st.session_state.setdefault('report_from_v2',today.replace(day=1))
    st.session_state.setdefault('report_to_v2',today)
    ownership,vehicle='Both','All'
    chosen={}
    if applied:applied['details']={k:v for k,v in applied.get('details',{}).items() if k!='capacity'}
    with st.container(key='report_filters'),st.form('report_filter_form',border=False):
        if kind=='P&L':
            dates_col, ownership_col, vehicle_col, apply_col=st.columns([1.8,2.2,1.6,1],vertical_alignment='bottom')
            with dates_col:
                c1,c2=st.columns(2,gap='small')
                start=c1.date_input('Records from',value=None,format='DD/MM/YYYY',key='report_from_v2',min_value=OPERATIONS_START)
                end=c2.date_input('Records to',value=None,format='DD/MM/YYYY',key='report_to_v2',min_value=OPERATIONS_START)
            st.session_state.setdefault('pnl_ownership_filter',pnl['ownership'])
            if st.session_state.get('pnl_vehicle_filter') not in vehicle_options:st.session_state['pnl_vehicle_filter']=pnl['vehicle']
            with ownership_col:
                ownership=st.segmented_control('Vehicle Type',['Both','Own','Outside','Vehicle No. Wise'],default='Both',key='pnl_ownership_filter') or 'Both'
            with vehicle_col:
                vehicle=st.selectbox('Vehicle No.',vehicle_options,key='pnl_vehicle_filter')
            with apply_col:
                submitted=st.form_submit_button('Apply Filter',type='primary',key='apply_report_filters',icon=':material/filter_alt:',use_container_width=True)
        else:
            specs=[('branch','Branch',_options(rows,'branch'))]
            if kind=='DTR':
                specs += [('company','Company Name',_options(rows,'company_name')),
                    ('ownership','Ownership',['All','Own','Outside'])]
            else:
                specs += [('transporter','Transporter',_options(rows,'transporter_name')),
                    ('status','Payment Status',['All','Pending','RTGS Done'])]
            cols=st.columns([1.65,*([1.4]*len(specs)),1],vertical_alignment='bottom',gap='small')
            dates=cols[0].date_input('Date Range',value=(applied['start'],applied['end']),format='DD/MM/YYYY',key=f"report_date_range_v4_{kind}_{applied['start']}_{applied['end']}",min_value=OPERATIONS_START)
            start,end=(dates[0],dates[-1]) if isinstance(dates,(tuple,list)) and len(dates)==2 else (None,None)
            labels={'branch':'All Branches','company':'All Companies','capacity':'All Types','ownership':'All (Own & Outside)',
                'transporter':'All Transporters','status':'All (Pending & Paid)'}
            for col,(field,label,options) in zip(cols[1:],specs):
                key=f'report_{kind}_{field}_v4'
                if switched or st.session_state.get(key) not in options:st.session_state[key]=choices.get(field,'All') if choices.get(field,'All') in options else 'All'
                chosen[field]=col.selectbox(label,options,key=key,format_func=lambda v,f=field:labels[f] if v=='All' else v)
            with cols[-1]:submitted=st.form_submit_button('Apply Filter',icon=':material/filter_alt:',type='primary',key='apply_report_filters',use_container_width=True)
    valid=start is not None and end is not None and start<=end
    if submitted or requested:
        if not valid:
            st.error('Select a complete valid date range. Your previous report is still shown.')
        else:
            applied={'user':user,'start':start,'end':end,'kind':kind,'ownership':ownership,'vehicle':vehicle,'details':chosen}
            st.session_state['report_applied_filters']=applied
            if kind!='P&L':
                st.session_state['report_from_v2']=start
                st.session_state['report_to_v2']=end
            if kind=='P&L':st.session_state['report_applied_pnl']={'user':user,'ownership':ownership,'vehicle':vehicle}
            st.session_state['report_applied_details']={**details,kind:chosen}
    return applied,bool((submitted or requested) and valid)


def filter_report_rows(rows, filters):
    fields={'branch':'branch','company':'company_name','capacity':'vehicle_capacity','transporter':'transporter_name','ownership':'ownership_type'}
    details={k:v for k,v in filters.get('details',{}).items() if k!='capacity'}
    result=list(rows)
    for choice,field in fields.items():
        value=details.get(choice,'All')
        if value!='All':result=[r for r in result if str(r.get(field) or '').strip().casefold()==value.casefold()]
    status=details.get('status','All')
    if status!='All':result=[r for r in result if bool(r.get('rtgs_done'))==(status=='RTGS Done')]
    return result
