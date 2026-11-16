"""Transporter balance workspace: review trips, match paid money, queue the remainder."""
import datetime as dt
import hashlib
import html
import uuid
from zoneinfo import ZoneInfo
from decimal import Decimal
import pandas as pd
import streamlit as st
from .payment_settlement import obj,money,suggest_allocations,settlement_view
from .number_format import format_inr
from .operational_dates import OPERATIONS_START
from .branch_names import canonical_branch


def today(): return dt.datetime.now(ZoneInfo('Asia/Kolkata')).date()
def esc(v): return html.escape(str(v or ''))
def currency(v): return format_inr(float(v))
def identity(row): return row.get('_pending_transporter_name') or row.get('transporter_name') or 'Transporter not specified'
def key_for(name): return hashlib.sha256(name.encode()).hexdigest()[:12]


def styles():
    st.markdown('''<style>
    .bw-title{display:flex;align-items:center;gap:16px;margin:12px 0 24px;color:#0a1534}.bw-title .bw-symbol{display:grid;place-items:center;width:62px;height:62px;background:#def6e9;border-radius:18px;color:#08722b;font-size:34px;font-weight:800}.bw-title h2{margin:0;padding:0;font-size:29px;color:#0a1534}.bw-title p{margin:5px 0 0;color:#536383;font-size:14px}
    .bw-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:18px 0 24px}.bw-stat{padding:21px 16px;border-radius:17px;border:1px solid #dde8ff;background:linear-gradient(125deg,#fbfdff,#eaf1ff);color:#101c38;min-height:125px}.bw-stat:nth-child(2){background:linear-gradient(125deg,#fff,#eaf8f0);border-color:#deefe6}.bw-stat:nth-child(3){background:#fff7ed;border-color:#f5e6d5}.bw-stat:nth-child(4){background:#f1edff;border-color:#e4dafa}.bw-stat:nth-child(5){background:#effaf2;border-color:#d9eee0}.bw-stat small{display:block;font-size:12px;font-weight:650;margin-bottom:12px}.bw-stat strong{display:block;font-size:clamp(18px,1.8vw,27px);letter-spacing:-.5px;overflow-wrap:anywhere}.bw-stat span{font-size:11px;color:#667896}
    [class*="st-key-bw_panel"]{background:linear-gradient(130deg,#fff,#f9fbff);border:1px solid #e1e9fb!important;border-radius:23px;padding:20px!important;box-shadow:0 5px 20px #1b49a009}
    .bw-person{display:flex;align-items:center;gap:14px;margin-bottom:15px}.bw-avatar{display:grid;place-items:center;width:50px;height:50px;flex-shrink:0;border-radius:50%;background:#daf5e4;color:#126332;font-size:25px;font-weight:800}.bw-person h3{margin:0;padding:0;font-size:23px;color:#0a1737}.bw-person small{color:#5a6a83;font-size:12px}
    .bw-mini{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:10px 0 18px}.bw-mini>div{background:#eef4ff;border:1px solid #e2eafb;border-radius:13px;padding:12px;color:#172542}.bw-mini>div:nth-child(2){background:#ecfaf2;color:#0d7232}.bw-mini>div:nth-child(3){background:#fff0f1;color:#b02128}.bw-mini small{display:block;font-size:12px;margin-bottom:8px}.bw-mini strong{font-size:20px;overflow-wrap:anywhere}
    .bw-paid{color:#087d29}.bw-outstanding{color:#b51922}
    .bw-stat-icon{float:left;width:35px;height:35px;padding:7px;background:#ffffffb0;border-radius:10px;margin:0 10px 10px 0;color:#086dff}.bw-stat-icon svg{width:100%;height:100%}
    .st-key-bw_modes button{height:68px!important;border-radius:16px!important;box-shadow:none!important;text-align:left!important;border:1px solid #e0e7f7!important;color:#111c34!important;background:#fff!important}.st-key-bw_modes button[kind="primary"]{background:linear-gradient(120deg,#e5faed,#cef2df)!important;border-color:#65cf98!important;color:#075b26!important}
    [class*="st-key-bw_transporter_"] button{border:1px solid #e4eaf5!important;border-radius:11px!important;background:#fff!important;box-shadow:none!important;justify-content:flex-start!important;min-height:47px!important;overflow-wrap:anywhere}.st-key-bw_panel_list button[kind="primary"]{background:#e4f7ec!important;color:#145b34!important;border-color:#88d3a4!important}
    [class*="st-key-bw_green"] button{background:linear-gradient(110deg,#178849,#006d2d)!important;border:0!important;color:white!important;border-radius:12px!important;box-shadow:none!important}
    .bw-note{padding:12px 15px;border:1px solid #e0e9ff;border-radius:12px;color:#586b85;font-size:12px;background:#f5f9ff;margin:12px 0}.bw-dialog-title{font-size:25px;font-weight:800;color:#101c3b;margin:0 0 6px}.bw-subtitle{color:#66758c;font-size:13px;margin-bottom:20px}
    .st-key-bw_panel_detail .stTabs [data-baseweb="tab-list"],[data-testid="stDialog"]:has(.bw-dialog-title) .stTabs [data-baseweb="tab-list"]{position:static!important;inset:auto!important;z-index:auto!important;width:100%!important;max-width:100%!important;height:auto!important;justify-content:flex-start!important;gap:16px!important;padding:0!important;margin:0 0 12px!important;background:transparent!important;box-shadow:none!important;border:0!important;border-bottom:1px solid #e0e8fa!important;border-radius:0!important;overflow-x:auto!important;overflow-y:hidden!important}
    .st-key-bw_panel_detail .stTabs [data-testid="stTab"],[data-testid="stDialog"]:has(.bw-dialog-title) .stTabs [data-testid="stTab"]{position:relative!important;inset:auto!important;width:auto!important;flex:0 0 auto!important;border-radius:0!important;border:0!important;min-height:43px!important;height:43px!important;padding:8px 10px!important;background:transparent!important;box-shadow:none!important;transform:none!important;color:#172442!important;font-size:13px!important}
    .st-key-bw_panel_detail .stTabs [data-testid="stTab"]:before,.st-key-bw_panel_detail .stTabs [data-testid="stTab"]:after,[data-testid="stDialog"]:has(.bw-dialog-title) .stTabs [data-testid="stTab"]:before,[data-testid="stDialog"]:has(.bw-dialog-title) .stTabs [data-testid="stTab"]:after{display:none!important;content:none!important}
    .st-key-bw_panel_detail .stTabs [data-testid="stTab"][aria-selected="true"],[data-testid="stDialog"]:has(.bw-dialog-title) .stTabs [data-testid="stTab"][aria-selected="true"]{border-bottom:3px solid #0066ff!important;background:transparent!important;border-radius:0!important;box-shadow:none!important;color:#0059ff!important}
    .st-key-bw_panel_detail .stTabs [data-baseweb="tab-panel"],[data-testid="stDialog"]:has(.bw-dialog-title) .stTabs [data-baseweb="tab-panel"]{padding:8px 0!important}
    [data-testid="stDialog"]:has(.bw-dialog-title) [role="dialog"]{width:min(1160px,96vw)!important;max-width:1160px!important;max-height:92vh;overflow-y:auto;border-radius:22px!important}
    [data-testid="stDialog"]:has(.bw-dialog-title) h2{display:none!important}
    [data-testid="stDialog"]:has(.bw-dialog-title) [data-testid="stMetricValue"]{font-size:24px!important}
    [data-testid="stDialog"]:has(.bw-dialog-title) [data-baseweb="input"]>div,[data-testid="stDialog"]:has(.bw-dialog-title) [data-baseweb="select"]>div{background:#fff!important;border:1px solid #dce4f4!important;border-radius:9px!important}
    [class*="st-key-bw_close"] button{border:0!important;background:transparent!important;min-width:34px!important;width:34px!important;padding:0!important;box-shadow:none!important;font-size:0!important}
    [data-testid="stDialog"]:has(.bw-dialog-title) button[kind="primary"]{background:#087b34!important;color:#fff!important;border:0!important;border-radius:11px!important}
    .st-key-bw_mobile_picker{display:none}
    @media(max-width:900px){.bw-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.bw-mini{grid-template-columns:repeat(2,minmax(0,1fr))}[class*="st-key-bw_panel"]{padding:12px!important}.st-key-bw_mobile_picker{display:block}.st-key-bw_desktop_picker{display:none}.st-key-bw_panel_list [data-testid="stTextInput"]{display:none}}
    </style>''',unsafe_allow_html=True)


def mini(rows):
    values=[('Total Payable',currency(sum(r['_payable'] for r in rows))),('Paid Till Date',currency(sum(r['_paid'] for r in rows))),('Outstanding',currency(sum(r['_outstanding'] for r in rows))),('Trips',str(len(rows)))]
    st.markdown('<div class="bw-mini">'+''.join(f'<div><small>{k}</small><strong>{esc(v)}</strong></div>' for k,v in values)+'</div>',unsafe_allow_html=True)


def trip_frame(rows,select=False):
    result=[]
    for r in rows:
        entry={'Record / Trip':r['request_number'],'Trip Date':r['trip_date'],'Branch':canonical_branch(r.get('branch')),
               'Route':f"{r.get('from_location') or ''} → {r.get('to_location') or ''}",'Vehicle No.':r.get('vehicle_number',''),
               'Payable (BP)':float(r['_payable']),'Paid Amount':float(r['_paid']),'Outstanding':float(r['_outstanding']),
               'Awaiting Confirmation':float(r['_awaiting']),'Available for RTGS':float(r['_sendable']),'Status':r['_settlement_status']}
        if select: entry={'Select':False,**entry}
        result.append(entry)
    return pd.DataFrame(result)


def number_columns():
    return {k:st.column_config.NumberColumn(k,format='₹%.2f') for k in ('Payable (BP)','Paid Amount','Outstanding','Awaiting Confirmation','Available for RTGS','Allocate Payment (₹)')}


def styled_trips(frame):
    if frame.empty: return frame
    def status(value):
        return {'Pending':'background-color:#fff0c8;color:#925100',
                'Partially Paid':'background-color:#dfebff;color:#155bd2',
                'Cleared':'background-color:#dff6e5;color:#087329'}.get(value,'')
    return frame.style.map(status,subset=['Status']).map(lambda v:'color:#13803b',subset=['Paid Amount']).map(lambda v:'color:#ba222a',subset=['Outstanding'])


def history_contents(rows,queues,records,user,store,scope):
    numbers={r['request_number'] for r in rows}
    payments=[p for p in records if any(a['record'] in numbers for a in obj(p['snapshot']).get('allocations',[]))]
    batches={}
    for q in queues:
        raw=obj(q['rtgs_data']);n=raw.get('_source_request_number',q['request_number'])
        if n in numbers: batches.setdefault(raw.get('_settlement_batch') or 'Legacy · '+q['request_number'],[]).append(q)
    _,confirmed=settlement_view([],queues,records)
    tabs=st.tabs([f'Payment Records ({len(payments)})',f'RTGS Batches ({len(batches)})','Trip Settlement'])
    with tabs[0]:
        if not payments: st.info('No actual payments have been recorded for these trips yet.')
        payment_page=st.selectbox('Payment records page',range(1,max(1,(len(payments)+7)//8)+1),key=f'payments_page_{scope}') if len(payments)>8 else 1
        for p in payments[(payment_page-1)*8:payment_page*8]:
            snapshot=obj(p['snapshot'])
            with st.expander(f"{p['payment_date']:%d %b %Y} · {currency(p['amount'])} · Recorded by {p['user_name']}"):
                st.caption(f"Payment ID: {p['id']} · Reference: {snapshot.get('reference') or '—'}")
                st.dataframe(pd.DataFrame([{'Record / Trip':a['record'],'Paid Amount':float(money(a['amount'])),'Linked RTGS Requests':', '.join(a.get('queues',{})) or 'External payment'} for a in snapshot['allocations']]),hide_index=True,width='stretch')
    with tabs[1]:
        if not batches: st.info('No balance RTGS batches have been requested for these trips.')
        batch_page=st.selectbox('RTGS batches page',range(1,max(1,(len(batches)+7)//8)+1),key=f'batches_page_{scope}') if len(batches)>8 else 1
        for batch,items in sorted(batches.items(),key=lambda p:max(str(q['created_at']) for q in p[1]),reverse=True)[(batch_page-1)*8:batch_page*8]:
            total=sum(money(q['amount']) for q in items);paid=sum(confirmed.get(q['request_number'],Decimal(0)) for q in items);left=max(Decimal(0),total-paid)
            with st.expander(f"{batch} · {currency(total)} · {'Payment Recorded' if not left else 'Awaiting Confirmation'}"):
                st.caption(f"Requested by {items[0]['requested_by']} · Sent {str(items[0]['created_at'])[:16]}")
                st.dataframe(pd.DataFrame([{'Record / Trip':obj(q['rtgs_data']).get('_source_request_number',q['request_number']),'Batch Amount':float(q['amount']),'Confirmed Paid':float(confirmed.get(q['request_number'],Decimal(0))),'Remaining':float(max(Decimal(0),money(q['amount'])-confirmed.get(q['request_number'],Decimal(0))))} for q in items]),hide_index=True,width='stretch')
                if left:
                    with st.form(f'confirm_batch_{scope}_{key_for(batch)}'):
                        date=st.date_input('Actual bank payment date',value=today(),min_value=OPERATIONS_START,max_value=today())
                        acknowledged=st.checkbox('I confirm this remaining batch amount has actually been paid by the bank.')
                        save=st.form_submit_button('Confirm Payment Received / Paid',type='primary')
                    if save:
                        if not acknowledged: st.error('Confirm actual payment before saving.')
                        else:
                            allocations={}
                            for q in items:
                                n=obj(q['rtgs_data']).get('_source_request_number',q['request_number']);amt=max(Decimal(0),money(q['amount'])-confirmed.get(q['request_number'],Decimal(0)))
                                allocations[n]=allocations.get(n,Decimal(0))+amt
                            try:
                                store.save_matched_payment(user,left,date,allocations,'PAY-'+uuid.uuid4().hex,reference='Confirmed '+batch,queue_only={q['request_number'] for q in items})
                            except ValueError as exc: st.error(str(exc))
                            else: st.session_state['bw_notice']='Bank payment confirmed. Trip balances updated.';st.rerun()
    with tabs[2]:
        search,status=st.columns([3,1])
        query=search.text_input('Search by trip / vehicle / route',key=f'history_search_{scope}')
        status_value=status.selectbox('Status',['All Statuses','Pending','Partially Paid','Cleared'],key=f'history_status_{scope}')
        shown=[r for r in rows if (status_value=='All Statuses' or r['_settlement_status']==status_value) and (not query or query.casefold() in ' '.join(str(r.get(k,'')) for k in ('request_number','vehicle_number','from_location','to_location')).casefold())]
        st.dataframe(styled_trips(trip_frame(shown)),hide_index=True,width='stretch',column_config=number_columns())
        st.caption(f'{len(shown)} trips · Status is calculated from actual saved payment allocations.')


@st.dialog('Payment History',width='large',dismissible=False)
def payment_history(name,rows,queues,records,user,store):
    title,close=st.columns([12,1])
    title.markdown(f'<div class="bw-dialog-title">Payment History – {esc(name)}</div><div class="bw-subtitle">Complete record of payments, RTGS batches and trip-wise settlement.</div>',unsafe_allow_html=True)
    with close,st.container(key='bw_close_history'):
        if st.button('Close',icon=':material/close:',key='bw_history_close',help='Close Payment History'): st.rerun()
    mini(rows)
    history_contents(rows,queues,records,user,store,'popup_'+key_for(name))


@st.dialog('Match Payment',width='large',dismissible=False)
def match_payment(name,rows,user,store,token):
    title,close=st.columns([12,1])
    title.markdown(f'<div class="bw-dialog-title">Match Payment – {esc(name)}</div><div class="bw-subtitle">Record money actually paid and allocate it to one or more trips, in full or in part.</div>',unsafe_allow_html=True)
    with close,st.container(key='bw_close_match'):
        if st.button('Close',icon=':material/close:',key='bw_match_close',help='Close Match Payment'): st.rerun()
    total=sum(r['_outstanding'] for r in rows)
    with st.container(border=True):
        st.markdown('**Payment Details**')
        a,b=st.columns(2)
        value=a.number_input('Payment Amount (₹)',min_value=0.0,step=100.0,value=0.0,key=f'match_value_{token}')
        date=b.date_input('Payment Date',value=today(),min_value=OPERATIONS_START,max_value=today(),key=f'match_date_{token}')
        reference=st.text_input('Payment reference / note',key=f'match_reference_{token}')
    suggestions=suggest_allocations(rows,value)
    st.caption('Suggested allocations use exact matches first, then oldest trips. Review or change them below.')
    if value>float(total): st.warning('This payment exceeds the outstanding balance. Enter only the amount to allocate to these trips.')
    if st.button('Auto Match Suggestions',icon=':material/auto_fix_high:',key=f'auto_match_{token}'):
        st.session_state[f'match_revision_{token}']=st.session_state.get(f'match_revision_{token}',0)+1
    signature=key_for(str(value)+'_'+str(st.session_state.get(f'match_revision_{token}',0)))
    with st.form(f'match_form_{token}_{signature}'):
        left,right=st.columns([3,1])
        frame=[]
        for r in sorted(rows,key=lambda r:(str(r['trip_date']),r['request_number'])):
            n=r['request_number'];suggestion=suggestions.get(n,Decimal(0))
            frame.append({'Select':bool(suggestion),'Record / Trip':n,'Trip Date':r['trip_date'],'Payable (BP)':float(r['_payable']),'Paid Amount':float(r['_paid']),'Outstanding':float(r['_outstanding']),'Allocate Payment (₹)':float(suggestion)})
        with left:
            st.markdown('**Allocate to Trips**')
            edited=st.data_editor(pd.DataFrame(frame),hide_index=True,width='stretch',disabled=['Record / Trip','Trip Date','Payable (BP)','Paid Amount','Outstanding'],column_config={**number_columns(),'Allocate Payment (₹)':st.column_config.NumberColumn('Allocate Payment (₹)',min_value=0.0,step=.01)},key=f'match_grid_{token}_{signature}')
        with right:
            st.markdown('**Allocation Summary**')
            st.metric('Payment Amount',currency(value))
            st.metric('Suggested Allocation',currency(sum(suggestions.values())))
            st.caption('The exact selected allocations are validated on Save. No money is moved by this action.')
        st.info('Use this only for money actually paid. Saving automatically updates Pending → Partially Paid / Cleared.')
        cancel,save=st.columns([1,1])
        cancelled=cancel.form_submit_button('Cancel',use_container_width=True)
        submitted=save.form_submit_button('Save Payment',type='primary',use_container_width=True)
    if cancelled: st.rerun()
    if submitted:
        try:
            allocated={r['Record / Trip']:r['Allocate Payment (₹)'] for r in edited.to_dict('records') if r['Select']}
            if any(money(v)<0 for v in allocated.values()): raise ValueError('Allocations cannot be negative.')
            store.save_matched_payment(user,value,date,allocated,token,reference)
        except ValueError as exc: st.error(str(exc))
        else: st.session_state['bw_notice']='Payment saved. Trip balances and statuses updated.';st.rerun()


def render_balance_workspace(user,store):
    from .pending_payments import payment_groups,transporter_key,view_balance_bills
    styles()
    if st.session_state.get('bw_notice'): st.success(st.session_state.pop('bw_notice'))
    rows,queues,records=store.settlement_snapshot(user)
    heading,period=st.columns([3,1],vertical_alignment='center')
    heading.markdown('<div class="bw-title"><div class="bw-symbol">₹</div><div><h2>Pending Payments</h2><p>Manage Balance Payments, UPI and Billtee payments, send for RTGS and track settlements.</p></div></div>',unsafe_allow_html=True)
    start=st.session_state.get('bw_from',OPERATIONS_START)
    end=st.session_state.get('bw_to',today())
    with period.popover(f'{start:%d %b} – {end:%d %b %Y}',icon=':material/calendar_month:',use_container_width=True):
        st.caption('Date and branch filters')
        start=st.date_input('Trips from',value=OPERATIONS_START,min_value=OPERATIONS_START,key='bw_from')
        end=st.date_input('Trips to',value=today(),min_value=OPERATIONS_START,key='bw_to')
        branch=st.selectbox('Branch',['All Branches','Andheri','Wada','Pune','Vadodara'],key='bw_branch')
    with st.container(key='bw_modes'):
        for col,label,kind,icon in zip(st.columns(3),['Balance Payments','UPI','Billtee'],['balance','upi','billtee'],['local_shipping','directions_car','receipt_long']):
            col.button(label,icon=f':material/{icon}:',type='primary' if kind=='balance' else 'secondary',use_container_width=True,key=f'bw_mode_{kind}',on_click=st.session_state.update,args=({'pending_kind_card':kind},))
    if start>end: st.error('Choose an end date on or after the start date.');return
    filtered=[r for r in rows if start<=r['trip_date']<=end and (branch=='All Branches' or canonical_branch(r.get('branch'))==branch)]
    # Group on original payable, not outstanding, so cleared trips remain available in history.
    groups=payment_groups([{**r,'balance_amount':float(r['_payable'])} for r in filtered],'balance',{}, {})
    total=sum(r['_outstanding'] for r in filtered);awaiting=sum(r['_awaiting'] for r in filtered)
    numbers={r['request_number'] for r in filtered}
    sent_queues=[q for q in queues if obj(q['rtgs_data']).get('_source_request_number',q['request_number']) in numbers]
    sent=sum(money(q['amount']) for q in sent_queues)
    batches={obj(q['rtgs_data']).get('_settlement_batch') or q['request_number'] for q in sent_queues}
    period_paid=sum(money(a['amount']) for p in records if start<=p['payment_date']<=end for a in obj(p['snapshot']).get('allocations',[]) if a['record'] in {r['request_number'] for r in filtered})
    cards=[('Pending Trips',str(sum(r['_outstanding']>0 for r in filtered)),'Trips with a remaining balance'),('Total Outstanding',currency(total),'Unpaid balance across selected trips'),('Sent for RTGS',currency(sent),f'{len(sent_queues)} requests in {len(batches)} batches'),('Awaiting Confirmation',currency(awaiting),f"{sum(r['_awaiting']>0 for r in filtered)} trips awaiting payment"),('Cleared (This Period)',currency(period_paid),'Actual payments recorded in this period')]
    from .sid_entry_design import PATHS
    icons=[PATHS['truck'],PATHS['coins'],'<path d="m3 3 18 9-18 9 4-9-4-9Zm4 9h14"/>','<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>','<path d="m5 12 4 4L19 6"/>']
    st.markdown('<div class="bw-grid">'+''.join(f'<div class="bw-stat"><div class="bw-stat-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">{icon}</svg></div><small>{a}</small><strong>{esc(b)}</strong><span>{c}</span></div>' for (a,b,c),icon in zip(cards,icons))+'</div>',unsafe_allow_html=True)
    sidebar,detail=st.columns([1,2.15],gap='medium')
    with sidebar,st.container(border=True,key='bw_panel_list'):
        st.markdown(f'### Transporters ({len(groups)})')
        search=st.text_input('Search transporter',placeholder='Search transporter…',label_visibility='collapsed',key='bw_search')
        show_cleared=st.checkbox('Include fully cleared transporters',value=False,key='bw_show_cleared')
        visible=[g for g in groups if (show_cleared or any(i['trip']['_outstanding']>0 for i in g)) and (not search or transporter_key(search) in transporter_key(' '.join(i['name']+' '+i.get('search_name','') for i in g)))]
        visible.sort(key=lambda g:-sum(i['trip']['_outstanding'] for i in g))
        group_map={key_for(g[0]['name']):g for g in visible}
        selected=st.session_state.get('bw_group')
        if selected not in group_map: selected=next(iter(group_map),None);st.session_state['bw_group']=selected
        with st.container(key='bw_mobile_picker'):
            st.session_state['bw_mobile_group']=selected
            def mobile_choice(): st.session_state['bw_group']=st.session_state['bw_mobile_group']
            st.selectbox('Transporter',list(group_map),format_func=lambda k:group_map[k][0]['name'],key='bw_mobile_group',on_change=mobile_choice)
        with st.container(key='bw_desktop_picker'):
            pages=max(1,(len(visible)+7)//8)
            page=min(max(1,st.session_state.get('bw_page',1)),pages)
            previous,position,next_page=st.columns([1,2,1])
            if previous.button('‹',disabled=page==1,key='bw_prev'):
                st.session_state['bw_page']=page-1;st.rerun(scope='fragment')
            position.caption(f'Page {page} of {pages}')
            if next_page.button('›',disabled=page==pages,key='bw_next'):
                st.session_state['bw_page']=page+1;st.rerun(scope='fragment')
            for g in visible[(int(page)-1)*8:int(page)*8]:
                name=g[0]['name'];key=key_for(name);out=sum(i['trip']['_outstanding'] for i in g)
                with st.container(key=f'bw_transporter_{key}'):
                    if st.button(f'{name}  ·  {len(g)} trips  ·  {currency(out)}',type='primary' if selected==key else 'secondary',use_container_width=True,key=f'bw_pick_{key}'):
                        st.session_state['bw_group']=key;st.rerun(scope='fragment')
    with detail,st.container(border=True,key='bw_panel_detail'):
        if not selected: st.info('No transporters match the selected filters.');return
        group=group_map[selected];name=group[0]['name'];group_rows=[i['trip'] for i in group]
        a,b,c=st.columns([2.5,1.1,1.1])
        profiles={tuple(str(i['profile'].get(k) or '') for k in ('BNF_NAME','BENE_ACC_NO','BENE_IFSC')) for i in group}
        bank=next(iter(profiles)) if len(profiles)==1 else None
        caption=f'Beneficiary: {bank[0] or "Not provided"}  |  A/c: {bank[1] or "Missing"}  |  IFSC: {bank[2] or "Missing"}' if bank else 'Multiple saved beneficiaries — each trip keeps its own bank details.'
        a.markdown(f'<div class="bw-person"><div class="bw-avatar">{esc(name[:1])}</div><div><h3>{esc(name)}</h3><small>{esc(caption)}</small></div></div>',unsafe_allow_html=True)
        open_match=b.button('Match Payment',icon=':material/currency_rupee:',key='bw_match',use_container_width=True,disabled=not any(r['_outstanding']>0 for r in group_rows))
        open_history=c.button('Payment History',icon=':material/menu_book:',key='bw_history',use_container_width=True)
        mini(group_rows)
        tabs=st.tabs([f'Trips ({len(group_rows)})','RTGS Batches / Payments','Print Bills'])
        with tabs[0]:
            status=st.selectbox('Trip status',['Pending / Partially Paid','All Statuses','Pending','Partially Paid','Cleared'],key='bw_trip_status')
            shown=[r for r in group_rows if status=='All Statuses' or (r['_outstanding']>0 if status=='Pending / Partially Paid' else r['_settlement_status']==status)]
            with st.form('bw_send_form_'+selected):
                frame=trip_frame(shown,True)
                if not frame.empty:
                    edited=st.data_editor(styled_trips(frame),hide_index=True,width='stretch',disabled=[c for c in frame if c!='Select'],column_config=number_columns(),key='bw_grid_'+selected)
                else: edited=frame;st.info('No trips match this status.')
                st.caption('Only the remaining amount not already awaiting confirmation is sent. Select trips, then send for RTGS.')
                with st.container(key='bw_green_send'):
                    send=st.form_submit_button('Send for RTGS',icon=':material/send:',type='primary',disabled=frame.empty)
            if send:
                try:
                    by_number={r['request_number']:r for r in group_rows}
                    selected_rows={r['Record / Trip']:{'amount':r['Available for RTGS'],'updated_at':by_number[r['Record / Trip']].get('updated_at')} for r in edited.to_dict('records') if r['Select']}
                    store.queue_settlement_rtgs(user,selected_rows,'RTGS-'+uuid.uuid4().hex)
                except ValueError as exc: st.error(str(exc))
                else: st.session_state['bw_notice']='Sent for RTGS. Awaiting actual payment confirmation.';st.rerun()
        with tabs[1]: history_contents(group_rows,queues,records,user,store,'main_'+selected)
        with tabs[2]:
            bills=store.list_balance_bills(user)
            from .pending_payments import transporter_key
            matching=[bill for bill in bills if transporter_key(bill['transporter_name'])==transporter_key(name)]
            if st.button('Print Bill',icon=':material/print:',disabled=not matching,key='bw_print'): view_balance_bills(matching,store,user)
        if open_match: match_payment(name,[r for r in group_rows if r['_outstanding']>0],user,store,'PAY-'+uuid.uuid4().hex)
        elif open_history: payment_history(name,group_rows,queues,records,user,store)
    st.markdown('<div class="bw-note">Match Payment records actual paid money. RTGS requests remain awaiting confirmation. Trip freight, costs, DTR and P&L figures are unchanged.</div>',unsafe_allow_html=True)
