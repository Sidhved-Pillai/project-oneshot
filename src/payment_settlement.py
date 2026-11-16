"""Actual balance settlements, kept separate from trip costs and RTGS requests."""
import datetime as dt
import json
import uuid
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
from sqlalchemy import MetaData, Table, Column, String, Text, Date, DateTime, Numeric, select, insert
from .payment_access import PENDING_PAYMENT_USERS

metadata = MetaData()
payment_records = Table('balance_settlement_records', metadata,
    Column('id', String(40), primary_key=True), Column('user_name', String(120), nullable=False),
    Column('payment_date', Date, nullable=False), Column('amount', Numeric(14,2), nullable=False),
    Column('created_at', DateTime, nullable=False), Column('snapshot', Text, nullable=False))


def obj(v):
    return v if isinstance(v,dict) else json.loads(v or '{}')


def money(v):
    try:
        result=Decimal(str(v or 0))
        if not result.is_finite(): raise ValueError('Enter a valid amount.')
        return result.quantize(Decimal('.01'))
    except (InvalidOperation,TypeError): raise ValueError('Enter a valid amount.')


def profile_view(trips, closings):
    """Retain approved names/banks, never substitute the retired opening balances."""
    from .pending_payments import transporter_key
    rows=[dict(r) for r in trips]
    for closing in closings:
        snapshot=obj(closing['snapshot'])
        aliases={transporter_key(n) for n in snapshot.get('aliases',[])}
        for row in rows:
            if row.get('report_scope')=='Expense': continue
            if transporter_key(row.get('transporter_name') or obj(row.get('dtr_data')).get('Transporter Name')) not in aliases: continue
            row['_pending_transporter_name']=closing['transporter_name']
            if snapshot.get('approved_payment_profile'):
                row['rtgs_data']=dict(snapshot['approved_payment_profile'])
                row['beneficiary_name']=row['rtgs_data']['BNF_NAME']
    return rows


def settlement_view(trips, queues, records):
    paid={}; confirmed={}
    for record in records:
        for a in obj(record['snapshot']).get('allocations',[]):
            n=a['record']; paid[n]=paid.get(n,Decimal(0))+money(a['amount'])
            for q,value in a.get('queues',{}).items(): confirmed[q]=confirmed.get(q,Decimal(0))+money(value)
    waiting={}
    for q in queues:
        raw=obj(q['rtgs_data']); n=raw.get('_source_request_number',q['request_number'])
        # Retired synthetic carry-forward records are not trip settlements.
        if n.startswith('BALREC-'): continue
        left=max(Decimal(0),money(q['amount'])-confirmed.get(q['request_number'],Decimal(0)))
        waiting[n]=waiting.get(n,Decimal(0))+left
    result=[]
    for trip in trips:
        if trip.get('report_scope')=='Expense' or trip.get('is_archived') or trip.get('status')=='Cancelled' or str(trip.get('ownership_type') or '').lower().startswith('own'): continue
        total=max(Decimal(0),money(trip.get('balance_amount')))
        if not total: continue
        n=trip['request_number']; settled=paid.get(n,Decimal(0)); left=max(Decimal(0),total-settled)
        reserved=min(left,waiting.get(n,Decimal(0)))
        result.append({**trip,'_payable':total,'_paid':settled,'_outstanding':left,'_awaiting':reserved,
                       '_sendable':max(Decimal(0),left-reserved),
                       '_settlement_status':'Cleared' if not left else 'Partially Paid' if settled else 'Pending'})
    return result,confirmed


def suggest_allocations(rows,value):
    remaining=money(value); result={}
    # Exact matches first, then oldest outstanding trips; user reviews before saving.
    ordered=sorted(rows,key=lambda r:(money(r['_outstanding'])!=remaining,str(r['trip_date']),r['request_number']))
    for r in ordered:
        allocated=min(remaining,money(r['_outstanding']))
        if allocated>0: result[r['request_number']]=allocated; remaining-=allocated
    return result


class SettlementStore:
    def settlement_snapshot(self,user):
        self._settlement_access(user)
        from .request_store import requests,REQUEST_METADATA_COLUMNS,balance_payments,balance_reconciliations
        with self.engine.connect() as c:
            trips=[dict(r) for r in c.execute(select(*REQUEST_METADATA_COLUMNS).where(requests.c.is_archived.is_(False),requests.c.status!='Cancelled')).mappings()]
            queues=[dict(r) for r in c.execute(select(balance_payments)).mappings()]
            records=[dict(r) for r in c.execute(select(payment_records).order_by(payment_records.c.created_at.desc())).mappings()]
            closings=[dict(r) for r in c.execute(select(balance_reconciliations)).mappings()]
        rows,_=settlement_view(profile_view(trips,closings),queues,records)
        return rows,queues,records

    @staticmethod
    def _settlement_access(user):
        if user not in PENDING_PAYMENT_USERS: raise ValueError('You do not have access to Pending Payments.')

    def _locked_settlement(self,c,numbers):
        from .request_store import requests,REQUEST_METADATA_COLUMNS,balance_payments,balance_reconciliations
        trips=[dict(r) for r in c.execute(select(*REQUEST_METADATA_COLUMNS).where(requests.c.request_number.in_(numbers)).order_by(requests.c.request_number).with_for_update()).mappings()]
        queues=[dict(r) for r in c.execute(select(balance_payments).order_by(balance_payments.c.request_number)).mappings()]
        records=[dict(r) for r in c.execute(select(payment_records)).mappings()]
        closings=[dict(r) for r in c.execute(select(balance_reconciliations)).mappings()]
        viewed,confirmed=settlement_view(profile_view(trips,closings),queues,records)
        return {r['request_number']:r for r in viewed},queues,confirmed

    def save_matched_payment(self,user,value,date,allocations,token,reference='',queue_only=None):
        self._settlement_access(user)
        from .request_store import activity_logs
        value=money(value)
        if value<=0: raise ValueError('Payment amount must be greater than zero.')
        if not isinstance(date,dt.date) or isinstance(date,dt.datetime) or date>dt.datetime.now(ZoneInfo('Asia/Kolkata')).date(): raise ValueError('Choose the actual payment date, not a future date.')
        from .operational_dates import OPERATIONS_START
        if date<OPERATIONS_START: raise ValueError('Choose a payment date in the operating period.')
        if any(money(v)<0 for v in allocations.values()): raise ValueError('Allocations cannot be negative.')
        allocation={str(n):money(v) for n,v in allocations.items() if money(v)>0}
        if not allocation or sum(allocation.values())!=value: raise ValueError('Allocate the entire payment amount exactly to the selected trips.')
        if len(token)>40 or not token: raise ValueError('Invalid payment identifier.')
        with self.engine.begin() as c:
            rows,queues,confirmed=self._locked_settlement(c,sorted(allocation))
            existing=c.execute(select(payment_records).where(payment_records.c.id==token)).mappings().first()
            if existing:
                if money(existing['amount'])!=value or obj(existing['snapshot']).get('requested_allocations')!={n:str(v) for n,v in allocation.items()}:
                    raise ValueError('This payment was already saved with different details. Reopen Match Payment.')
                return False
            if set(rows)!=set(allocation): raise ValueError('A selected trip is unavailable. Refresh and review.')
            from .pending_payments import payment_groups
            if len(payment_groups(list(rows.values()),'balance',{},{}))!=1: raise ValueError('Select trips from one transporter only.')
            saved=[]
            for n,amt in allocation.items():
                if amt>rows[n]['_outstanding']: raise ValueError('An allocation exceeds the current outstanding balance. Refresh and review.')
                if date<rows[n]['trip_date']: raise ValueError('Payment date cannot precede the selected trip date.')
                linked={}; remaining=amt
                for q in sorted(queues,key=lambda q:(str(q['created_at']),q['request_number'])):
                    if queue_only and q['request_number'] not in queue_only: continue
                    source=obj(q['rtgs_data']).get('_source_request_number',q['request_number'])
                    if source!=n: continue
                    take=min(remaining,max(Decimal(0),money(q['amount'])-confirmed.get(q['request_number'],Decimal(0))))
                    if take:
                        linked[q['request_number']]=str(take); remaining-=take
                if queue_only and remaining: raise ValueError('Batch payment changed. Reopen Payment History.')
                saved.append({'record':n,'amount':str(amt),'queues':linked,'trip_date':str(rows[n]['trip_date']),
                              'transporter':rows[n].get('_pending_transporter_name') or rows[n].get('transporter_name')})
            c.execute(insert(payment_records).values(id=token,user_name=user,payment_date=date,amount=value,
                created_at=dt.datetime.now(ZoneInfo('Asia/Kolkata')).replace(tzinfo=None),
                snapshot=json.dumps({'reference':reference,'allocations':saved,'requested_allocations':{n:str(v) for n,v in allocation.items()}},default=str)))
            c.execute(insert(activity_logs).values(user_name=user,action='Matched balance payment',request_number=token,
                details=json.dumps({'payment_date':str(date),'amount':str(value),'allocations':saved,'reference':reference})))
        return True

    def reverse_matched_payment(self,user,payment_id,token,reason):
        """Correct a mistaken ledger payment with a reversible, audited entry."""
        self._settlement_access(user)
        from .request_store import activity_logs
        if not str(reason or '').strip(): raise ValueError('Enter a reason for the correction.')
        if not token or len(token)>40: raise ValueError('Invalid correction identifier.')
        with self.engine.begin() as c:
            original=c.execute(select(payment_records).where(payment_records.c.id==payment_id)).mappings().first()
            if not original or money(original['amount'])<=0: raise ValueError('Select an original payment to reverse.')
            allocations=obj(original['snapshot'])['allocations']
            self._locked_settlement(c,sorted(a['record'] for a in allocations))
            records=[dict(r) for r in c.execute(select(payment_records)).mappings()]
            if any(r['id']==token for r in records): return False
            if any(obj(r['snapshot']).get('reversal_of')==payment_id for r in records):
                raise ValueError('This payment has already been reversed.')
            reversed_allocations=[{**a,'amount':str(-money(a['amount'])),
                'queues':{q:str(-money(value)) for q,value in a.get('queues',{}).items()}} for a in allocations]
            snapshot={'reversal_of':payment_id,'reference':str(reason).strip(),'allocations':reversed_allocations}
            c.execute(insert(payment_records).values(id=token,user_name=user,
                payment_date=dt.datetime.now(ZoneInfo('Asia/Kolkata')).date(),amount=-money(original['amount']),
                created_at=dt.datetime.now(ZoneInfo('Asia/Kolkata')).replace(tzinfo=None),snapshot=json.dumps(snapshot)))
            c.execute(insert(activity_logs).values(user_name=user,action='Corrected balance payment',request_number=token,
                details=json.dumps({'original_payment':payment_id,'reason':str(reason).strip(),
                    'amount':str(-money(original['amount'])),'allocations':reversed_allocations})))
        return True

    def queue_settlement_rtgs(self,user,selected,token):
        self._settlement_access(user)
        from .request_store import balance_payments,activity_logs,balance_bills
        if not selected: raise ValueError('Select trips with an outstanding amount available to send.')
        with self.engine.begin() as c:
            rows,queues,_=self._locked_settlement(c,sorted(selected))
            if any(obj(q['rtgs_data']).get('_settlement_batch')==token for q in queues): return 0
            if set(rows)!=set(selected): raise ValueError('A selected trip is unavailable.')
            from .pending_payments import payment_groups
            if len(payment_groups(list(rows.values()),'balance',{},{}))!=1: raise ValueError('Select one transporter at a time.')
            bill=[];queue_ids={}
            for n,expected in sorted(selected.items()):
                row=rows[n]; amt=money(row['_sendable'])
                if isinstance(expected,dict):
                    if str(row.get('updated_at'))!=str(expected.get('updated_at')):
                        raise ValueError('A selected trip or its bank details changed. Refresh and review before sending.')
                    expected=expected['amount']
                if amt<=0 or amt!=money(expected): raise ValueError('The available balance changed. Refresh and review before sending.')
                profile=obj(row.get('rtgs_data')).copy()
                profile['BNF_NAME']=profile.get('BNF_NAME') or row.get('beneficiary_name','')
                if not all(str(profile.get(k) or '').strip() for k in ('BNF_NAME','BENE_ACC_NO','BENE_IFSC')): raise ValueError('Complete bank details before sending this trip.')
                qid='BPQ-'+uuid.uuid4().hex
                profile.update(AMOUNT=float(amt),_source_request_number=n,_settlement_batch=token,_payment_kind='balance',_payment_id='BALANCE:'+qid)
                profile['REMARK']=str(profile.get('REMARK') or row.get('notes') or '')+' Balance Payment'
                profile['Origin Area']=row.get('branch','')
                c.execute(insert(balance_payments).values(request_number=qid,amount=amt,rtgs_data=json.dumps(profile),rtgs_done=False,requested_by=user))
                bill.append(({**row,'transporter_name':row.get('_pending_transporter_name') or row.get('transporter_name')},amt))
                queue_ids[n]=qid
            from .balance_bill_v3 import make_bill,totals,bill_group_key
            bill_groups={}
            for row,amt in bill: bill_groups.setdefault(bill_group_key(row),[]).append((row,amt))
            for items in bill_groups.values():
                snapshot=make_bill(items,user)
                snapshot['settlement_tracking']=True
                for item in snapshot['rows']: item['balance_queue_id']=queue_ids[item['request_number']]
                c.execute(insert(balance_bills).values(transporter_name=snapshot['transporter'],requested_by=user,
                    created_at=dt.datetime.now(ZoneInfo('Asia/Kolkata')).replace(tzinfo=None),trip_count=len(items),amount=totals(snapshot)['grand_total'],snapshot=json.dumps(snapshot,default=str)))
            c.execute(insert(activity_logs).values(user_name=user,action='Sent balance batch for RTGS',request_number=token,
                details=json.dumps({'message':'Awaiting payment confirmation; not marked paid.','allocations':{n:str(v.get('amount') if isinstance(v,dict) else v) for n,v in selected.items()}})))
        return len(bill)


def annotate_queues(payments,records):
    """Report outstanding requests without changing their original batch amount."""
    _,confirmed=settlement_view([],list(payments.values()),records)
    touched={q for r in records for a in obj(r['snapshot']).get('allocations',[]) for q in a.get('queues',{})}
    return {n:{**q,'_has_settlement_activity':n in touched,'_settled_amount':confirmed.get(n,Decimal(0)),
               '_awaiting_amount':max(Decimal(0),money(q['amount'])-confirmed.get(n,Decimal(0)))}
            for n,q in payments.items()}
