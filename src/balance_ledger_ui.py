"""Original transporter cards with an interactive, local-first ledger popup."""
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
from decimal import Decimal
import uuid
import streamlit as st
import streamlit.components.v1 as components
from .payment_settlement import obj,money,settlement_view
from .balance_workspace import today,currency
from .branch_names import canonical_branch
from .operational_dates import OPERATIONS_START
from .invoice_display import dtr_invoice_text

_ledger=components.declare_component('oneshot_balance_ledger',path=str(Path(__file__).with_name('balance_ledger_component')))


def row_payload(row):
    profile=obj(row.get('rtgs_data'))
    return {'id':row['request_number'],'invoice':dtr_invoice_text(obj(row.get('dtr_data')).get('Invoice No.') or row.get('invoice_number')) or row['request_number'],
            'date':str(row['trip_date'])[:10],'branch':canonical_branch(row.get('branch')),'vehicle':row.get('vehicle_number') or '',
            'route':f"{row.get('from_location') or ''} → {row.get('to_location') or ''}",
            'original':int(money(row['_payable'])*100),'paid':int(money(row['_paid'])*100),
            'outstanding':int(money(row['_outstanding'])*100),'sendable':int(money(row['_sendable'])*100),
            'awaiting':int(money(row['_awaiting'])*100),'status':row['_settlement_status'],
            'bankReady':all(str(profile.get(k) or (row.get('beneficiary_name') if k=='BNF_NAME' else '') or '').strip() for k in ('BNF_NAME','BENE_ACC_NO','BENE_IFSC'))}


def history_payload(rows,queues,records):
    numbers={r['request_number'] for r in rows}
    associated=[r for r in records if any(a['record'] in numbers for a in obj(r['snapshot']).get('allocations',[]))]
    reversed_ids={obj(r['snapshot']).get('reversal_of') for r in associated}
    history=[]
    for r in associated:
        raw=obj(r['snapshot'])
        history.append({'id':r['id'],'date':str(r['payment_date']),'created':str(r['created_at']),
            'user':r['user_name'],'amount':int(money(r['amount'])*100),'reference':raw.get('reference',''),
            'correctionOf':raw.get('reversal_of'),'reversed':r['id'] in reversed_ids,
            'allocations':[{'id':a['record'],'amount':int(money(a['amount'])*100)} for a in raw['allocations']]})
    _,confirmed=settlement_view([],queues,records)
    batches={}
    for q in queues:
        raw=obj(q['rtgs_data']);number=raw.get('_source_request_number',q['request_number'])
        if number not in numbers:continue
        batch=raw.get('_settlement_batch') or 'Legacy '+q['request_number']
        group=batches.setdefault(batch,{'id':batch,'date':str(q['created_at'])[:10],'user':q['requested_by'],'rows':[]})
        group['rows'].append({'id':number,'queueId':q['request_number'],'amount':int(money(q['amount'])*100),
                              'confirmed':int(confirmed.get(q['request_number'],Decimal(0))*100)})
    return history,sorted(batches.values(),key=lambda b:(b['date'],b['id']),reverse=True)


def ledger_action(store,user,action,rows,records,queues,token):
    """Validate all browser selections against this transporter's server snapshot."""
    by_number={r['request_number']:r for r in rows}
    kind=action.get('action')
    if kind=='save':
        submitted=action.get('payments') or {}
        if not isinstance(submitted,dict) or not submitted or not set(submitted)<=set(by_number):
            raise ValueError('Select valid trips from this transporter.')
        allocations={n:money(v) for n,v in submitted.items()}
        if any(v<=0 for v in allocations.values()): raise ValueError('Enter a positive Payment Now amount for each selected payment.')
        try:date=dt.date.fromisoformat(str(action.get('paymentDate')))
        except ValueError:raise ValueError('Choose the actual payment date.')
        return store.save_matched_payment(user,sum(allocations.values()),date,allocations,token,str(action.get('reference') or 'Ledger update'))
    if kind=='send':
        numbers=action.get('numbers') or []
        if not numbers or len(set(numbers))!=len(numbers) or not set(numbers)<=set(by_number): raise ValueError('Select valid trips to send.')
        selected={n:{'amount':by_number[n]['_sendable'],'updated_at':by_number[n].get('updated_at')} for n in numbers}
        return store.queue_settlement_rtgs(user,selected,token)
    if kind=='reverse':
        if action.get('paymentId') not in {r['id'] for r in records if any(a['record'] in by_number for a in obj(r['snapshot']).get('allocations',[]))}:
            raise ValueError('Select a payment associated with this transporter.')
        return store.reverse_matched_payment(user,action['paymentId'],token,str(action.get('reason') or ''))
    if kind=='confirm':
        history,batches=history_payload(rows,queues,records)
        batch=next((b for b in batches if b['id']==action.get('batchId')),None)
        if not batch:raise ValueError('This RTGS batch is unavailable.')
        if action.get('actuallyPaid') is not True: raise ValueError('Confirm that this money has actually been paid.')
        allocations={}
        for r in batch['rows']:
            remaining=max(0,r['amount']-r['confirmed'])
            if remaining: allocations[r['id']]=allocations.get(r['id'],Decimal(0))+Decimal(remaining)/100
        try: date=dt.date.fromisoformat(str(action.get('paymentDate')))
        except ValueError: raise ValueError('Choose the actual bank payment date.')
        return store.save_matched_payment(user,sum(allocations.values()),date,allocations,token,
            reference='Confirmed '+batch['id'],queue_only={r['queueId'] for r in batch['rows']})
    raise ValueError('Unknown ledger action.')


@st.dialog('Update in Ledger',width='large',dismissible=True,on_dismiss='ignore')
def update_in_ledger(name,rows,queues,records,user,store,instance):
    # The component owns only draft UI state; every committed amount is rechecked by the store.
    st.markdown('''<style>
    [data-testid="stDialog"]:has(.ledger-popup-marker) [role="dialog"]{width:min(1220px,97vw)!important;max-width:1220px!important;max-height:94vh;overflow-y:auto;background:linear-gradient(125deg,#fff,#f8fbff)!important;border-radius:22px!important;padding:12px!important}
    [data-testid="stDialog"]:has(.ledger-popup-marker) [role="dialog"]>div:first-child{display:none!important}
    [data-testid="stDialog"]:has(.ledger-popup-marker) [role="dialog"] button[aria-label="Close"]{visibility:hidden!important}
    [data-testid="stDialog"]:has(.ledger-popup-marker) [role="dialog"]>div:last-child{padding:8px 10px!important}
    [data-testid="stDialog"]:has(.ledger-popup-marker) iframe{width:100%!important;border:0!important}
    [data-testid="stDialog"]:has(.ledger-popup-marker) [data-testid="stVerticalBlock"]{gap:0!important}
    </style><span class="ledger-popup-marker"></span>''',unsafe_allow_html=True)
    history,batches=history_payload(rows,queues,records)
    signature=hashlib.sha256(json.dumps([row_payload(r) for r in rows],sort_keys=True,default=str).encode()).hexdigest()
    response=st.session_state.get('ledger_response_'+instance)
    result=_ledger(name=name,rows=[row_payload(r) for r in rows],history=history,batches=batches,
        today=str(today()),start=min((str(r['trip_date'])[:10] for r in rows),default=str(OPERATIONS_START)),
        signature=signature,response=response,key='ledger_component_'+instance,default=None)
    if not isinstance(result,dict):return
    nonce=result.get('nonce')
    if not isinstance(nonce,str) or not nonce or len(nonce)>150 or nonce==st.session_state.get('ledger_action_'+instance):return
    st.session_state['ledger_action_'+instance]=nonce
    if result.get('action')=='close':
        st.rerun()
    token=('COR-' if result.get('action')=='reverse' else 'RTGS-' if result.get('action')=='send' else 'PAY-')+hashlib.sha256((user+instance+nonce).encode()).hexdigest()[:32]
    try:
        ledger_action(store,user,result,rows,records,queues,token)
    except (ValueError,TypeError,ArithmeticError) as exc:
        st.session_state['ledger_response_'+instance]={'nonce':nonce,'error':str(exc)}
        st.rerun(scope='fragment')
    else:
        st.session_state['pending_payment_notice']={'save':'Payment updates saved. Trip balances and statuses are updated.','send':'Sent eligible trips for RTGS. Actual payment confirmation is still required.','reverse':'Payment corrected with an audited reversal.','confirm':'Actual bank payment confirmed.'}[result['action']]
        st.rerun()


def render_balance_cards(user,trips,upi_requests,store):
    from .pending_payments import render_payment_styles,summary_cards,pending_summary,payment_groups,transporter_key,view_balance_bills
    render_payment_styles()
    st.markdown('''<style>
    .pp-summary-card{min-height:135px!important;padding:18px!important}.pp-summary-grid{margin-bottom:18px!important}
    .pp-summary-label{min-height:30px!important}.pp-summary-copy strong{font-size:27px!important}
     .st-key-ledger_filters [data-testid="stForm"]{border:0!important;padding:0!important}
    .st-key-ledger_filters [data-baseweb="select"]>div,.st-key-ledger_filters [data-baseweb="input"]{background:#fff!important;border:1px solid #dce5f5!important;border-radius:12px!important;min-height:43px!important}
    @media(min-width:1001px){
      .st-key-ledger_modes{width:36%!important}
      .st-key-ledger_filters{margin-top:-59px!important}
      .st-key-ledger_filters [data-testid="stForm"]>[data-testid="stVerticalBlock"]>[data-testid="stLayoutWrapper"]:first-child{margin-left:40%!important;width:60%!important}
    }
    @media(max-width:700px){
      .st-key-ledger_modes [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:8px!important}
      .st-key-ledger_modes [data-testid="stColumn"]{min-width:0!important;width:auto!important;flex:1 1 0!important}
      .st-key-ledger_modes [data-testid="stColumn"]:first-child{flex:1.8 1 0!important}
      .st-key-ledger_modes button{padding:6px!important;font-size:12px!important}
      .st-key-ledger_modes button p{font-size:12px!important}
      [class*="st-key-ledger_card_"]>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:minmax(0,1fr)!important;gap:9px!important}
      [class*="st-key-ledger_card_"]>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{width:100%!important;min-width:0!important}
      [class*="st-key-ledger_card_"]>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:nth-child(3){grid-column:1/-1!important}
      [class*="st-key-ledger_card_"]>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:nth-child(4){grid-column:1/-1!important}
    }
    .st-key-ledger_modes button{border-radius:24px!important;min-height:43px!important;border:1px solid #dce6f5!important;background:white!important;box-shadow:none!important}
    .st-key-ledger_modes button[kind="primary"]{background:linear-gradient(120deg,#e4faed,#d2f3e3)!important;color:#0b6930!important;border-color:#80d7a5!important}
    [class*="st-key-ledger_card_"]{border:1px solid #dbe5f8!important;border-radius:17px!important;padding:9px 14px!important;margin-bottom:5px!important;background:linear-gradient(125deg,#fff,#f8faff)!important;box-shadow:0 3px 9px #174cc90a!important}
    [class*="st-key-ledger_update_"] button{background:linear-gradient(110deg,#178b25,#006c19)!important;color:white!important;border:0!important;border-radius:11px!important;min-height:42px!important;box-shadow:0 3px 5px #006b1720!important;white-space:nowrap!important}
    [class*="st-key-ledger_print_"] button{background:#fff!important;border:1px solid #d4def0!important;color:#101b3c!important;border-radius:11px!important;min-height:42px!important;white-space:nowrap!important}
    .st-key-ledger_apply button{background:linear-gradient(110deg,#2289ff,#0055ff)!important;color:white!important;border:0!important;min-height:43px!important;border-radius:11px!important}
    @media(max-width:700px){.pp-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:8px!important}.pp-summary-card{padding:12px!important;min-height:140px!important}.pp-summary-card .pp-summary-icon{display:none!important}.pp-summary-copy strong{font-size:21px!important}.pp-summary-label{font-size:11px!important}}
    </style>''',unsafe_allow_html=True)
    if st.session_state.get('pending_payment_notice'):st.success(st.session_state.pop('pending_payment_notice'))
    rows,queues,records=store.settlement_snapshot(user)
    overall=pending_summary(trips,{},upi_requests)
    overall['balance']={'count':sum(r['_sendable']>0 for r in rows),'amount':sum((r['_sendable'] for r in rows),Decimal(0))}
    summary_cards(overall)
    with st.container(key='ledger_modes'):
        cols=st.columns([1.6,.85,.9],gap='small')
        for c,label,kind,icon in zip(cols[:3],['Balance Payment','UPI','Billtee'],['balance','upi','billtee'],['local_shipping','directions_car','receipt_long']):
            c.button(label,icon=f':material/{icon}:',type='primary' if kind=='balance' else 'secondary',use_container_width=True,key='ledger_kind_'+kind,on_click=st.session_state.update,args=({'pending_kind_card':kind},))
    groups=payment_groups([{**r,'balance_amount':float(r['_payable'])} for r in rows],'balance',{}, {})
    with st.container(key='ledger_filters'),st.form('ledger_filter_form',border=False):
        search_col,branch_col,sort_col=st.columns([2.1,1.6,2.2])
        search=search_col.selectbox('Search transporter', sorted({g[0]['name'] for g in groups},key=str.casefold),index=None,accept_new_options=True,placeholder='Search transporter…',label_visibility='collapsed',key='ledger_search')
        branch=branch_col.selectbox('Branch',['All Branches','Andheri','Pune','Vadodara','Wada'],label_visibility='collapsed',key='ledger_branch')
        sort=sort_col.selectbox('Sort by',['Total Amount (High to Low)','Name'],label_visibility='collapsed',key='ledger_sort')
        a,b,apply_col=st.columns([2.4,2.4,1.1],vertical_alignment='bottom')
        start=a.date_input('Trips From',value=OPERATIONS_START,min_value=OPERATIONS_START,format='DD/MM/YYYY',key='ledger_from')
        end=b.date_input('Trips To',value=today(),min_value=OPERATIONS_START,format='DD/MM/YYYY',key='ledger_to')
        with apply_col,st.container(key='ledger_apply'):
            apply=st.form_submit_button('Apply Filter',icon=':material/filter_list:',type='primary',use_container_width=True)
    if apply or 'ledger_applied' not in st.session_state:
        st.session_state['ledger_applied']=(search or '',branch,sort,start,end)
        st.session_state['ledger_page']=1
    search,branch,sort,start,end=st.session_state['ledger_applied']
    if start>end:st.error('Choose an end date on or after the start date.');return
    show_cleared=st.toggle('Include cleared transporters for payment history',value=False,key='ledger_include_cleared')
    visible=[]
    for g in groups:
        match=[i for i in g if start<=i['trip']['trip_date']<=end and (branch=='All Branches' or canonical_branch(i['trip'].get('branch'))==branch)]
        if not match:continue
        if not show_cleared and not any(i['trip']['_outstanding']>0 for i in match):continue
        if search and transporter_key(search) not in transporter_key(' '.join(i['name']+' '+i.get('search_name','') for i in g)):continue
        visible.append((g,match))
    visible.sort(key=lambda pair:-sum(i['trip']['_outstanding'] for i in pair[1]) if sort.startswith('Total') else pair[0][0]['name'].casefold())
    st.caption(f"{sum(len(m) for _,m in visible)} trips · {len(visible)} transporters · {currency(sum(i['trip']['_outstanding'] for _,m in visible for i in m))}")
    if not visible:st.info('No payments match these filters.');return
    bills=store.list_balance_bills(user)
    pages=max(1,(len(visible)+14)//15);page=min(max(st.session_state.get('ledger_page',1),1),pages)
    for group,matching in visible[(page-1)*15:page*15]:
        name=group[0]['name'];key=hashlib.sha256(name.encode()).hexdigest()[:14]
        total=sum(i['trip']['_outstanding'] for i in matching);last=max(i['trip']['trip_date'] for i in matching)
        with st.container(key='ledger_card_'+key):
            identity,amount,print_col,update_col=st.columns([4,2.1,1.45,1.9],gap='small',vertical_alignment='center')
            identity.markdown(f'<div class="pp-identity"><div class="pp-avatar">{html.escape(name[:1].upper())}</div><div><div class="pp-name">{html.escape(name)}</div><div class="pp-meta">{len(matching)} trips · Last entry: {last:%d %b %Y}</div></div></div>',unsafe_allow_html=True)
            amount.markdown(f'<div class="pp-total"><span>Total Balance Amount</span><strong>{currency(total)}</strong></div>',unsafe_allow_html=True)
            matching_bills=[bill for bill in bills if transporter_key(bill['transporter_name']) in {transporter_key(name),*(transporter_key(i.get('search_name','')) for i in group)}]
            with print_col,st.container(key='ledger_print_'+key):
                if st.button('Print Bill',icon=':material/print:',disabled=not matching_bills,use_container_width=True,key='ledger_print_button_'+key):view_balance_bills(matching_bills,store,user)
            with update_col,st.container(key='ledger_update_'+key):
                if st.button('Update in Ledger',icon=':material/edit:',use_container_width=True,key='ledger_update_button_'+key):
                    update_in_ledger(name,[i['trip'] for i in group],queues,records,user,store,uuid.uuid4().hex)
    if pages>1:
        numbers=sorted({1,pages,*range(max(1,page-2),min(pages,page+2)+1)})
        with st.container(key='pending_pagination'):
            cols=st.columns([1.3,*([.5]*len(numbers)),1.3])
            cols[0].button('← Prev',disabled=page==1,key='ledger_prev',on_click=st.session_state.update,args=({'ledger_page':page-1},))
            for col,n in zip(cols[1:-1],numbers):
                col.button(str(n),type='primary' if n==page else 'secondary',key=f'ledger_page_{n}',on_click=st.session_state.update,args=({'ledger_page':n},))
            cols[-1].button('Next →',disabled=page==pages,key='ledger_next',on_click=st.session_state.update,args=({'ledger_page':page+1},))
