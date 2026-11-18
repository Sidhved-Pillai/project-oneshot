from copy import deepcopy
from types import SimpleNamespace
import pandas as pd
from src.report_status import persist_status_edits


def test_status_changes_write_only_changed_records_and_keep_each_payment_kind_separate():
    rows=[{'request_number':number,'rtgs_done':False,'rtgs_advance':100,'rtgs_data':{'REMARK':'keep me'}}
          for number in ['REQ-1','BALANCE:REQ-1','UPI:REQ-1','BILLTEE:REQ-1']]
    snapshot=([deepcopy(rows[0])],{'REQ-1':{'rtgs_done':False}},{'REQ-1':{'rtgs_done':False}})
    metadata=([],{'REQ-1':{'rtgs_done':False}})
    calls=[]
    store=SimpleNamespace(mark_rtgs_done=lambda numbers,**kwargs:calls.append((numbers,kwargs)))
    edited=pd.DataFrame({'RTGS Status':['RTGS Done','Pending','RTGS Done','RTGS Done']})
    assert persist_status_edits(store,rows,edited,'Shyam',snapshot,metadata)==3
    assert calls==[(['REQ-1','UPI:REQ-1','BILLTEE:REQ-1'],{'done':True,'edited_by':'Shyam'})]
    assert snapshot[0][0]['rtgs_done'] and snapshot[2]['REQ-1']['rtgs_done'] and metadata[1]['REQ-1']['rtgs_done']
    assert not snapshot[1]['REQ-1']['rtgs_done']
    assert all(row['rtgs_data']=={'REMARK':'keep me'} and row['rtgs_advance']==100 for row in rows)
    assert persist_status_edits(store,rows,edited,'Shyam',snapshot,metadata)==0
    assert len(calls)==1
    edited.loc[0,'RTGS Status']='Pending'
    assert persist_status_edits(store,rows,edited,'Shyam',snapshot,metadata)==1
    assert calls[-1]==(['REQ-1'],{'done':False,'edited_by':'Shyam'})


def test_status_edit_persists_without_touching_money_or_remarks(tmp_path):
    import datetime as dt
    from src.request_store import RequestStore
    from tests.test_pending_payments import trip
    store=RequestStore('sqlite:///'+str(tmp_path/'status.db'))
    number=trip(store,trip_date=dt.date(2026,11,17),rtgs_advance=1500)
    before=store.get(number)
    rows=[dict(before)]
    edited=pd.DataFrame({'RTGS Status':['RTGS Done']})
    snapshot=(rows,{},{});metadata=([],{})
    assert persist_status_edits(store,rows,edited,'Shyam',snapshot,metadata)==1
    after=store.get(number)
    assert after['rtgs_done']
    for field in ['rtgs_advance','balance_amount','revenue','notes','rtgs_data','dtr_data']:
        assert after.get(field)==before.get(field)
    edited.loc[0,'RTGS Status']='Pending'
    persist_status_edits(store,rows,edited,'Shyam',snapshot,metadata)
    assert not store.get(number)['rtgs_done']


def test_mark_for_later_persists_independently_and_returns_to_pending(tmp_path):
    from sqlalchemy import insert, select
    from src.request_store import RequestStore, balance_payments, upi_payments, billtee_payments
    from tests.test_pending_payments import trip
    from src.report_filters import filter_report_rows
    store=RequestStore('sqlite:///'+str(tmp_path/'later.db'))
    number=trip(store,rtgs_advance=1500)
    with store.engine.begin() as conn:
        for table in (balance_payments,upi_payments,billtee_payments):
            conn.execute(insert(table).values(request_number=number,amount=100,rtgs_data='{}',requested_by='Sid'))
    ids=[number,'BALANCE:'+number,'UPI:'+number,'BILLTEE:'+number]
    rows=[{'request_number':n,'rtgs_done':False} for n in ids]
    edited=pd.DataFrame({'RTGS Status':['Mark for Later']*4})
    assert persist_status_edits(store,rows,edited,'Sid',([],{},{}),([],{ }))==4
    assert filter_report_rows(rows,{'details':{'status':'Pending'}})==[]
    assert len(filter_report_rows(rows,{'details':{'status':'Mark for Later'}}))==4
    assert store.get(number)['rtgs_later']
    with store.engine.connect() as conn:
        for table in (balance_payments,upi_payments,billtee_payments):
            saved=conn.execute(select(table)).mappings().one()
            assert saved['rtgs_later'] and not saved['rtgs_done']
    edited.loc[0,'RTGS Status']='Pending'
    persist_status_edits(store,rows,edited,'Sid',([],{},{}),([],{}))
    assert not store.get(number)['rtgs_later']
    assert len(filter_report_rows(rows,{'details':{'status':'Pending'}}))==1
    store.mark_rtgs_done(ids,edited_by='Sid')
    assert store.get(number)['rtgs_done'] and not store.get(number)['rtgs_later']
