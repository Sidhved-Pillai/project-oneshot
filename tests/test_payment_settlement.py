import datetime as dt
import json
from decimal import Decimal
import pytest
from sqlalchemy import insert
from src.request_store import RequestStore,balance_payments,balance_reconciliations
from src.payment_settlement import settlement_view,profile_view,suggest_allocations,payment_records
from src.balance_payments import balance_rtgs_rows
from tests.test_pending_payments import trip


def setup(tmp_path):
    store=RequestStore(f'sqlite:///{tmp_path / "settlement.db"}')
    n=trip(store,trip_date=dt.date(2026,11,10))
    return store,n


def current(store,n):
    rows,_,_=store.settlement_snapshot('Sid')
    return next(r for r in rows if r['request_number']==n)


def test_partial_full_payment_is_audited_and_source_is_unchanged(tmp_path):
    store,n=setup(tmp_path);before=store.get(n)
    assert current(store,n)['_outstanding']==2000
    store.save_matched_payment('Nikhat',500,dt.date(2026,11,10),{n:500},'pay1','Bank reference')
    row=current(store,n)
    assert (row['_paid'],row['_outstanding'],row['_settlement_status'])==(500,1500,'Partially Paid')
    assert store.save_matched_payment('Nikhat',500,dt.date(2026,11,10),{n:500},'pay1') is False
    store.save_matched_payment('Shyam',1500,dt.date(2026,11,11),{n:1500},'pay2')
    assert current(store,n)['_settlement_status']=='Cleared'
    assert store.get(n)==before
    assert any(r['action']=='Matched balance payment' for r in store.list_activity_logs())


def test_rtgs_sending_and_download_done_are_not_payment_confirmation(tmp_path):
    store,n=setup(tmp_path)
    assert store.queue_settlement_rtgs('Nikhat',{n:2000},'batch1')==1
    assert store.queue_settlement_rtgs('Nikhat',{n:2000},'batch1')==0
    row=current(store,n)
    assert row['_paid']==0 and row['_awaiting']==2000 and row['_sendable']==0
    queued=store.list_balance_payments();qid=next(iter(queued))
    store.mark_rtgs_done(['BALANCE:'+qid],edited_by='Nikhat')
    assert current(store,n)['_settlement_status']=='Pending'
    assert current(store,n)['_paid']==0
    report=balance_rtgs_rows([store.get(n)],queued)
    assert len(report)==1 and report[0]['request_number']=='BALANCE:'+qid
    assert report[0]['vehicle_number']==store.get(n)['vehicle_number']
    with pytest.raises(ValueError): store.queue_settlement_rtgs('Sid',{n:2000},'batch2')


def test_partial_confirmation_reduces_reserved_amount_then_remaining_can_be_sent(tmp_path):
    store,n=setup(tmp_path)
    store.queue_settlement_rtgs('Sid',{n:2000},'batch1')
    qid=next(iter(store.list_balance_payments()))
    store.save_matched_payment('Sid',500,dt.date(2026,11,10),{n:500},'p1',queue_only={qid})
    row=current(store,n)
    assert row['_awaiting']==1500 and row['_outstanding']==1500 and row['_sendable']==0
    report=balance_rtgs_rows([store.get(n)],store.list_balance_payments())[0]
    assert report['rtgs_advance']==1500 and not report['rtgs_done']
    store.save_matched_payment('Nikhat',1500,dt.date(2026,11,11),{n:1500},'p2',queue_only={qid})
    assert current(store,n)['_settlement_status']=='Cleared'
    assert balance_rtgs_rows([store.get(n)],store.list_balance_payments())[0]['rtgs_done']
    store.update(n,{'balance_amount':2500})
    assert current(store,n)['_sendable']==500
    store.queue_settlement_rtgs('Nikhat',{n:500},'batch2')
    assert len(store.list_balance_payments())==2
    assert sum(q['amount'] for q in store.list_balance_payments().values())==2500


def test_manual_external_payment_then_queue_only_remaining(tmp_path):
    store,n=setup(tmp_path)
    store.save_matched_payment('Sid',750,dt.date(2026,11,10),{n:750},'p1')
    with pytest.raises(ValueError): store.queue_settlement_rtgs('Sid',{n:2000},'stale')
    assert not store.list_balance_payments()
    store.queue_settlement_rtgs('Sid',{n:1250},'remaining')
    assert next(iter(store.list_balance_payments().values()))['amount']==1250


@pytest.mark.parametrize('value,allocations',[(-1,{'n':-1}),(float('nan'),{'n':100}),(100,{'n':99}),(2001,{'n':2001}),(100,{'n':100,'bad':-1})])
def test_invalid_allocations_are_atomic(tmp_path,value,allocations):
    store,n=setup(tmp_path);allocations={n if k=='n' else k:v for k,v in allocations.items()}
    with pytest.raises(ValueError):store.save_matched_payment('Sid',value,dt.date(2026,11,10),allocations,'p1')
    assert current(store,n)['_paid']==0


def test_date_permissions_and_transporter_scope(tmp_path):
    store,n=setup(tmp_path)
    for date in (dt.date(2026,11,9),dt.date.today()+dt.timedelta(days=1)):
        with pytest.raises(ValueError):store.save_matched_payment('Sid',100,date,{n:100},'bad-date')
    for user in ('Vijay','Gopal','Manish'):
        with pytest.raises(ValueError):store.save_matched_payment(user,100,dt.date(2026,11,10),{n:100},'bad-user')
        with pytest.raises(ValueError):store.queue_settlement_rtgs(user,{n:2000},'bad-user')
    other=trip(store,trip_date=dt.date(2026,11,10),transporter_name='Different Transporter')
    with pytest.raises(ValueError):store.save_matched_payment('Sid',200,dt.date(2026,11,10),{n:100,other:100},'cross')
    store.update(n,{'is_archived':True})
    with pytest.raises(ValueError):store.save_matched_payment('Sid',100,dt.date(2026,11,10),{n:100},'archived')


def test_original_trip_balances_restored_and_approved_banks_retained(tmp_path):
    from tests.test_balance_reconciliation import closing
    store,n=setup(tmp_path)
    close=closing([n],99999)
    snapshot=json.loads(close['snapshot']);snapshot['approved_payment_profile']={'BNF_NAME':'Approved','BENE_ACC_NO':'00001','BENE_IFSC':'TEST0000001'}
    close['snapshot']=json.dumps(snapshot)
    with store.engine.begin() as c:c.execute(insert(balance_reconciliations).values(**close))
    row=current(store,n)
    assert row['_payable']==2000 and not row['request_number'].startswith('BALREC-')
    assert row['rtgs_data']['BNF_NAME']=='Approved'
    assert store.get(n)['rtgs_data']!=row['rtgs_data']


def test_legacy_done_request_still_requires_actual_payment_confirmation(tmp_path):
    store,n=setup(tmp_path)
    store.send_pending_payments({n:store.get(n)['updated_at']},'balance','Sid')
    store.mark_rtgs_done(['BALANCE:'+n],edited_by='Nikhat')
    assert current(store,n)['_paid']==0 and current(store,n)['_awaiting']==2000
    store.save_matched_payment('Sid',2000,dt.date(2026,11,10),{n:2000},'confirm',queue_only={n})
    assert current(store,n)['_settlement_status']=='Cleared'


def test_suggestions_exact_then_oldest_and_never_overallocate():
    rows=[{'request_number':'a','trip_date':'2026-10-01','_outstanding':Decimal(200)},
          {'request_number':'b','trip_date':'2026-10-02','_outstanding':Decimal(500)}]
    assert suggest_allocations(rows,500)=={'b':500}
    assert suggest_allocations(rows,600)=={'a':200,'b':400}


def test_workspace_dialogs_open_and_close(tmp_path):
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_string(f'''
from src.request_store import RequestStore
from src.pending_payments import render_pending_payments
from tests.test_pending_payments import trip
import streamlit as st
store=RequestStore({'sqlite:///'+str(tmp_path/'ui.db')!r})
if 'ready' not in st.session_state:
    trip(store)
    st.session_state['ready']=True
trips,balances,upi,_=store.dashboard_snapshot()
render_pending_payments('Sid',trips,balances,upi,store)
''').run()
    assert not app.exception
    next(b for b in app.button if (b.key or '').startswith('ledger_update_button_')).click().run()
    assert not app.exception
    component=app.get('component_instance')[0]
    payload=json.loads(component.proto.json_args)
    assert payload['name']=='Sai Transporter'
    assert payload['rows'][0]['outstanding']==200000
    assert payload['history']==[]
    # Switching modes still uses the original UPI / Billtee rendering.
    next(b for b in app.button if b.key=='ledger_kind_upi').click().run()
    assert not app.exception


def test_tracked_print_bill_uses_actual_settlement_not_download_flag(tmp_path):
    from src.balance_bill import payment_status
    store,n=setup(tmp_path)
    store.queue_settlement_rtgs('Sid',{n:2000},'print-batch')
    bill_id=store.list_balance_bills('Sid')[0]['id']
    qid=next(iter(store.list_balance_payments()))
    store.mark_rtgs_done(['BALANCE:'+qid],edited_by='Nikhat')
    assert 'awaiting payment confirmation' in payment_status(store.get_balance_bill(bill_id,'Sid'))
    store.save_matched_payment('Sid',500,dt.date(2026,11,10),{n:500},'print-part')
    assert 'Partially paid' in payment_status(store.get_balance_bill(bill_id,'Sid'))
    store.save_matched_payment('Sid',1500,dt.date(2026,11,10),{n:1500},'print-full')
    assert payment_status(store.get_balance_bill(bill_id,'Sid'))=='Payment confirmed'


def test_incomplete_second_bank_rolls_back_entire_batch(tmp_path):
    store,n=setup(tmp_path)
    other=trip(store,trip_date=dt.date(2026,11,10))
    store.update(other,{'rtgs_data':{}})
    with pytest.raises(ValueError):store.queue_settlement_rtgs('Nikhat',{n:2000,other:2000},'bad-bank')
    assert not store.list_balance_payments() and not store.list_balance_bills('Sid')


def test_stale_trip_or_bank_update_blocks_rtgs_submission(tmp_path):
    store,n=setup(tmp_path)
    old=store.get(n)
    store.update(n,{'beneficiary_name':'Updated beneficiary'})
    with pytest.raises(ValueError,match='changed'):
        store.queue_settlement_rtgs('Sid',{n:{'amount':2000,'updated_at':old['updated_at']}},'stale-bank')
    assert not store.list_balance_payments()


def test_transporter_with_two_bank_profiles_gets_separate_print_bills(tmp_path):
    store,n=setup(tmp_path)
    other=trip(store,trip_date=dt.date(2026,11,10))
    store.update(other,{'rtgs_data':{'BNF_NAME':'Other beneficiary','BENE_ACC_NO':'000222','BENE_IFSC':'TEST0000002'}})
    store.queue_settlement_rtgs('Sid',{n:2000,other:2000},'two-banks')
    bills=store.list_balance_bills('Sid')
    assert len(bills)==2
    assert {store.get_balance_bill(b['id'],'Sid')['profile']['BENE_ACC_NO'] for b in bills}=={'001234','000222'}


def test_ledger_correction_preserves_original_and_reopens_rtgs(tmp_path):
    store,n=setup(tmp_path);source=store.get(n)
    store.queue_settlement_rtgs('Sid',{n:2000},'queued')
    qid=next(iter(store.list_balance_payments()))
    store.mark_rtgs_done(['BALANCE:'+qid],edited_by='Sid')
    store.save_matched_payment('Nikhat',2000,dt.date(2026,11,10),{n:2000},'original',queue_only={qid})
    _,_,records=store.settlement_snapshot('Sid');original=next(r for r in records if r['id']=='original')
    assert store.reverse_matched_payment('Shyam','original','correction','Wrong payment reference')
    assert store.reverse_matched_payment('Shyam','original','correction','Retry') is False
    with pytest.raises(ValueError,match='already been reversed'):
        store.reverse_matched_payment('Sid','original','another','Retry with another ID')
    row=current(store,n)
    assert (row['_paid'],row['_outstanding'],row['_awaiting'],row['_sendable'])==(0,2000,2000,0)
    assert not balance_rtgs_rows([store.get(n)],store.list_balance_payments())[0]['rtgs_done']
    _,_,records=store.settlement_snapshot('Sid')
    assert next(r for r in records if r['id']=='original')==original
    assert next(r for r in records if r['id']=='correction')['amount']==-2000
    assert store.get(n)==source
    assert any(r['action']=='Corrected balance payment' for r in store.list_activity_logs())
    store.save_matched_payment('Nikhat',2000,dt.date(2026,11,10),{n:2000},'correct-payment',queue_only={qid})
    assert current(store,n)['_settlement_status']=='Cleared'


def test_ledger_reversal_requires_access_and_reason(tmp_path):
    store,n=setup(tmp_path)
    store.save_matched_payment('Sid',500,dt.date(2026,11,10),{n:500},'payment')
    with pytest.raises(ValueError):store.reverse_matched_payment('Vijay','payment','bad','Wrong reference')
    with pytest.raises(ValueError):store.reverse_matched_payment('Sid','payment','bad',' ')
    assert current(store,n)['_paid']==500


def test_popup_actions_are_scoped_and_use_actual_payment_confirmation(tmp_path):
    from src.balance_ledger_ui import ledger_action,history_payload
    store,n=setup(tmp_path);other=trip(store,transporter_name='Other Carrier')
    rows,queues,records=store.settlement_snapshot('Sid');rows=[r for r in rows if r['request_number']==n]
    with pytest.raises(ValueError):ledger_action(store,'Sid',{'action':'save','payments':{other:50},'paymentDate':'2026-11-10'},rows,records,queues,'bad')
    with pytest.raises(ValueError):ledger_action(store,'Sid',{'action':'send','numbers':[other]},rows,records,queues,'bad')
    ledger_action(store,'Sid',{'action':'save','payments':{n:500},'paymentDate':'2026-11-10'},rows,records,queues,'payment')
    rows,queues,records=store.settlement_snapshot('Sid');rows=[r for r in rows if r['request_number']==n]
    ledger_action(store,'Sid',{'action':'send','numbers':[n]},rows,records,queues,'queued')
    rows,queues,records=store.settlement_snapshot('Sid');rows=[r for r in rows if r['request_number']==n]
    history,batches=history_payload(rows,queues,records)
    assert history[0]['amount']==50000 and batches[0]['rows'][0]['amount']==150000
    action={'action':'confirm','batchId':'queued','paymentDate':'2026-11-10'}
    with pytest.raises(ValueError):ledger_action(store,'Sid',action,rows,records,queues,'confirmed')
    ledger_action(store,'Sid',{**action,'actuallyPaid':True},rows,records,queues,'confirmed')
    assert current(store,n)['_settlement_status']=='Cleared'
