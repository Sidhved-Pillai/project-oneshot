import copy
import datetime as dt
import json
from decimal import Decimal
import pytest
from sqlalchemy import insert
from src.request_store import RequestStore,balance_reconciliations
from src.balance_reconciliation import balance_view,reconciliation_row
from src.balance_payments import balance_rtgs_rows
from src.pending_payments import payment_groups,pending_summary,transporter_key
from tests.test_pending_payments import trip


def closing(numbers, amount=500,cutoff=dt.date(2026,10,29)):
    return dict(request_number='BALREC-test',transporter_name='Sai Transporter',cutoff=cutoff,
                amount=amount,updated_at=dt.datetime(2026,11,16),snapshot=json.dumps({
                    'aliases':['Sai Transporter'], 'covered_records':numbers,
                    'profile_row':{'branch':'Pune','beneficiary_name':'Test Transporter',
                    'rtgs_data':{'BNF_NAME':'Test Transporter','BENE_ACC_NO':'001234','BENE_IFSC':'TEST0000001'}}}))


def test_closing_balance_only_replaces_covered_trips_not_source_or_upi(tmp_path):
    store=RequestStore(f'sqlite:///{tmp_path / "view.db"}')
    old=trip(store)
    new=trip(store,trip_date=dt.date(2026,11,10))
    rows=[store.get(n) for n in (old,new)]
    original=copy.deepcopy(rows)
    viewed,credits=balance_view(rows,{},[closing([old])])
    assert not credits and {r['request_number'] for r in viewed}=={'BALREC-test',new}
    assert sum(i['amount'] for g in payment_groups(viewed,'balance',{}, {}) for i in g)==2500
    assert rows==original and store.get(old)==original[0]
    assert pending_summary(rows,{}, {},viewed)['upi']['amount']==Decimal('1000')


def test_credit_offsets_future_trips_once_and_queued_amount_reconciles(tmp_path):
    store=RequestStore(f'sqlite:///{tmp_path / "credit.db"}')
    old=trip(store)
    later=trip(store,trip_date=dt.date(2026,11,10))
    third=trip(store,trip_date=dt.date(2026,11,11))
    record=closing([old],-2500)
    with store.engine.begin() as conn:conn.execute(insert(balance_reconciliations).values(**record))
    viewed,credits=balance_view([store.get(n) for n in (old,later,third)],{},[record])
    assert not credits
    assert {r['request_number']:r['balance_amount'] for r in viewed}=={later:0,third:1500}
    before=store.get(third)
    assert store.send_pending_payments({third:before['updated_at']},'balance','Sid')==1
    assert store.list_balance_payments()[third]['amount']==1500
    assert store.get(third)==before
    viewed,credits=balance_view([store.get(n) for n in (old,later,third)],store.list_balance_payments(),[record])
    assert not credits and not any(i['status']=='Pending' for g in payment_groups(viewed,'balance',store.list_balance_payments(),{}) for i in g)
    with pytest.raises(ValueError):store.send_pending_payments({old:store.get(old)['updated_at']},'balance','Sid')


def test_confirmed_balance_queues_once_only_on_explicit_send_and_is_available_to_rtgs(tmp_path):
    store=RequestStore(f'sqlite:///{tmp_path / "opening.db"}')
    old=trip(store)
    record=closing([old],7000)
    with store.engine.begin() as conn:conn.execute(insert(balance_reconciliations).values(**record))
    assert not store.list_balance_payments()
    assert store.send_pending_payments({'BALREC-test':record['updated_at']},'balance','Nikhat')==1
    assert store.send_pending_payments({'BALREC-test':record['updated_at']},'balance','Nikhat')==0
    rows=balance_rtgs_rows([reconciliation_row(record)],store.list_balance_payments())
    assert len(rows)==1 and rows[0]['rtgs_advance']==7000
    store.mark_rtgs_done([rows[0]['request_number']],True,'Nikhat')
    assert store.list_balance_payments()['BALREC-test']['rtgs_done']
    assert len(store.list(status='All active'))==1


def test_later_payments_reduce_carryforward_and_remaining_credit_is_visible():
    rec=closing(['old'],3000)
    queued={'old':{'created_at':dt.datetime(2026,11,1),'amount':1000}}
    rows,credits=balance_view([],queued,[rec])
    assert rows[0]['balance_amount']==2000
    rows,credits=balance_view([],{},[closing([], -164000)])
    assert not rows and credits[0]['amount']==164000


def test_shree_spellings_group_and_bank_verified_typo_keeps_each_profile():
    rows=[{'request_number':str(i),'transporter_name':name,'balance_amount':100,'ownership_type':'Outside',
           'rtgs_data':{'BNF_NAME':str(i),'BENE_ACC_NO':'00123','BENE_IFSC':'test000001'}}
          for i,name in enumerate(['Shree Ganesh','Shri Ganesh','Shrii Ganesh'])]
    assert len(payment_groups(rows,'balance',{},{}))==1
    assert transporter_key('Shri Ganesh')==transporter_key('Shrii Ganesh')==transporter_key('Shree Ganesh')
    rows[0]['transporter_name']='Marwad Freight'
    rows[1]['transporter_name']='Marwad fright carrier'
    assert len(payment_groups(rows[:2],'balance',{},{}))==1
    rows[1]['rtgs_data']['BENE_ACC_NO']='other'
    assert len(payment_groups(rows[:2],'balance',{},{}))==2


def test_reconciled_balance_cannot_send_a_changed_display_amount(tmp_path):
    store=RequestStore(f'sqlite:///{tmp_path / "changed.db"}')
    old=trip(store)
    record=closing([old],7000)
    with store.engine.begin() as conn:conn.execute(insert(balance_reconciliations).values(**record))
    with pytest.raises(ValueError,match='balance changed'):
        store.send_pending_payments({'BALREC-test':{'updated_at':record['updated_at'],'amount':8000}},'balance','Sid')
    assert not store.list_balance_payments()


def test_ui_shows_opening_balance_not_covered_history_and_credits():
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_string('''
import streamlit as st
import datetime as dt
from src.pending_payments import render_pending_payments
from src.balance_reconciliation import reconciliation_row
class Store:
    def list_balance_reconciliations(self):
        return [dict(request_number='BALREC-ui',transporter_name='Shree Ganesh',cutoff=dt.date(2026,10,29),amount=7000,updated_at=dt.datetime(2026,11,16),snapshot={'aliases':['Shri Ganesh'],'covered_records':['old'],'profile_row':{'rtgs_data':{'BNF_NAME':'Test','BENE_ACC_NO':'00123','BENE_IFSC':'TEST0000001'}}})]
    def pending_upi_profiles(self,user): return {}
trips=[dict(request_number='old',transporter_name='Shri Ganesh',trip_date=dt.date(2026,10,29),balance_amount=2000,upi=500,updated_at=dt.datetime(2026,11,16),ownership_type='Outside')]
render_pending_payments('Sid',trips,{}, {},Store())
''').run()
    assert not app.exception
    next(b for b in app.button if str(b.key).startswith('pending_expand_')).click().run()
    assert not app.exception
    assert list(app.dataframe[0].value['Record'])==['BALREC-ui']
    assert list(app.dataframe[0].value['Balance'])==[7000]


def test_used_credit_is_not_released_if_source_trip_is_no_longer_in_active_view():
    rec=closing([], -2500)
    payments={'already-sent':{'amount':1500,'rtgs_data':{'_balance_reconciliation_id':'BALREC-test','_balance_credit_applied':1000}}}
    viewed,credits=balance_view([],payments,[rec])
    assert not viewed and credits[0]['amount']==1500


def test_explicitly_approved_pending_profile_does_not_modify_source():
    record=closing([], 100)
    snapshot=json.loads(record['snapshot'])
    snapshot['approved_payment_profile']={'BNF_NAME':'Approved', 'BENE_ACC_NO':'0001','BENE_IFSC':'TEST0000001'}
    record['snapshot']=json.dumps(snapshot)
    source={'request_number':'later','transporter_name':'Sai Transporter','trip_date':'2026-11-10','rtgs_data':{'BNF_NAME':'Old'}}
    viewed,_=balance_view([source],{},[record])
    assert viewed[0]['rtgs_data']==snapshot['approved_payment_profile']
    assert source['rtgs_data']=={'BNF_NAME':'Old'}
