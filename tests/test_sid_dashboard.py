import ast
import datetime as dt
import json
import re
from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from streamlit.testing.v1 import AppTest
from src.sid_dashboard import dashboard_summary
from src.pnl_report import branch_pnl_summary
from src.request_store import RequestStore, activity_logs
from src.expense_duplicates import expense_duplicate_signature


def finder():
    function = next(n for n in ast.parse(Path('app.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='duplicate_records')
    scope = {'re':re,'clean_text':lambda x:str(x or '').strip(),'as_date':lambda x:x,
             'number':lambda x:float(x or 0),'unpack':lambda x:json.loads(x) if isinstance(x,str) else x or {},
             'expense_duplicate_signature':expense_duplicate_signature}
    exec(compile(ast.Module(body=[function],type_ignores=[]),'finder','exec'),scope)
    return scope['duplicate_records']


def test_sid_navigation_replaces_entry_tabs_and_other_users_keep_theirs():
    tree=ast.parse(Path('app.py').read_text())
    navigation=next(n for n in tree.body if isinstance(n,ast.If) and any(isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='dashboard_tab' for target in x.targets for t in ast.walk(target)) for x in ast.walk(n)))
    for user, expected in [('Sid',['Dashboard','Records','Pending Payments','Generate Reports','Logs']),
                           ('Vinod',['Dashboard','New Entry','Direct Expenses','Records','Pending Payments','Generate Reports','Logs']),
                           ('Nikhil',['Dashboard','New Entry','Direct Expenses','Records','Pending Payments','Generate Reports','Logs']),
                           ('Ajit',['New Entry','Direct Expenses','Records','Pending Payments','Generate Reports','Logs']),
                           ('Nikhat',['Direct Expenses','Records','Pending Payments','Generate Reports','Logs'])]:
        labels=[]
        def tabs(names, **kwargs):
            labels.extend(names)
            return names
        scope={'current_user':user,'st':SimpleNamespace(tabs=tabs),'PENDING_PAYMENT_USERS':{'Sid','Nikhat','Ajit'}}
        exec(compile(ast.Module(body=[navigation],type_ignores=[]),'nav','exec'),scope)
        assert labels == expected
        if user=='Sid':
            assert scope['new_tab'] is scope['expense_tab'] is None


def test_counts_reconcile_and_finances_use_existing_reports():
    rows=[{'id':1,'request_number':'one','report_scope':'DTR','created_by':'Ajit','created_at':dt.datetime(2026,11,3,20),
           'trip_date':dt.date(2026,11,1),'branch':'wada','ownership_type':'Outside','revenue':20000,'transporter_freight':10000,'dtr_data':{}},
          {'id':2,'request_number':'two','report_scope':'Expense','created_by':'Nikhat','created_at':dt.datetime(2026,11,4,12),
           'trip_date':dt.date(2026,11,2),'branch':'Andheri','amount':2000,'dtr_data':{'categories':{'Salary':2000}}}]
    summary=dashboard_summary(rows,dt.date(2026,11,4),dt.date(2026,11,10),branch_pnl_summary)
    assert summary['total']==2  # UTC evening becomes the next calendar day in IST.
    assert sum(sum(c) for _,c in summary['branches'])==sum(sum(c) for _,c in summary['users'])==2
    assert summary['revenue']==20000 and summary['expense']==12000 and summary['profit']==8000
    assert summary['margin']==40 and summary['month_entries']==2
    summary=dashboard_summary(rows+[{**rows[0],'is_archived':True},{**rows[1],'status':'Cancelled'}],dt.date(2026,11,4),dt.date(2026,11,10),branch_pnl_summary)
    assert summary['total']==2 and summary['month_entries']==2


def seed(store):
    base={'report_scope':'DTR','trip_date':dt.date(2026,11,1),'vehicle_number':'MH01TEST','created_by':'Ajit',
          'branch':'Wada','invoice_number':'INV1','revenue':100,'status':'Verified'}
    return [store.create(base) for _ in range(3)]


def test_delete_only_selected_copies_with_atomic_audit_and_protected_original(tmp_path):
    store=RequestStore(f'sqlite:///{tmp_path / "duplicates.db"}')
    ids=seed(store)
    rows=[store.get(i) for i in ids]
    groups=finder()(rows,include_originals=True)
    assert groups[0]['original']['request_number']==ids[0] and len(groups[0]['duplicates'])==2
    versions={r['request_number']:str(r['updated_at']) for r in rows}
    with pytest.raises(ValueError,match='duplicate copy'):
        store.delete_duplicate_copies([ids[0]],versions,'Sid',finder())
    with pytest.raises(ValueError,match='Only Sid'):
        store.delete_duplicate_copies([ids[1]],versions,'Ajit',finder())
    assert store.delete_duplicate_copies([ids[1]],versions,'Sid',finder())==1
    assert not store.get(ids[0])['is_archived'] and store.get(ids[1])['is_archived']
    assert not store.get(ids[2])['is_archived']
    event=store.list_activity_logs()[0]
    assert event['user_name']=='Sid' and event['action']=='Deleted record'
    assert store.activity_details(event)['request_number']==ids[1]


def test_stale_selection_rejects_entire_delete_batch(tmp_path):
    store=RequestStore(f'sqlite:///{tmp_path / "stale.db"}')
    ids=seed(store)
    versions={i:str(store.get(i)['updated_at']) for i in ids}
    store.update(ids[2],{'invoice_number':'DIFFERENT'},'records_tab','Shyam')
    with pytest.raises(ValueError,match='changed'):
        store.delete_duplicate_copies(ids[1:],versions,'Sid',finder())
    assert all(not store.get(i)['is_archived'] for i in ids)


def dashboard_app():
    from src.sid_dashboard import render_dashboard
    from src.pnl_report import branch_pnl_summary
    render_dashboard('Sid',[],[],branch_pnl_summary,lambda groups:None)


def test_dashboard_empty_state_and_date_selection_render():
    app=AppTest.from_function(dashboard_app).run()
    assert not app.exception
    assert any(b.label=='Review Duplicates →' for b in app.button)
    assert any(b.label=='View P&L →' for b in app.button)
    assert len(app.date_input)==1


def test_view_pnl_applies_month_and_both_report_without_changing_other_users():
    source=ast.parse(Path('app.py').read_text())
    block=next(n for n in source.body if isinstance(n,ast.If) and 'dashboard_pnl_request' in ast.unparse(n.test))
    state={'dashboard_pnl_request':(dt.date(2026,11,1),dt.date(2026,11,30))}
    exec(compile(ast.Module(body=[block],type_ignores=[]),'pnl_request','exec'),
         {'current_user':'Sid','st':SimpleNamespace(session_state=state)})
    assert state['report_type']=='P&L' and state['pnl_ownership_filter']=='Both'
    assert state['report_from_v2']==dt.date(2026,11,1) and state['report_to_v2']==dt.date(2026,11,30)
    assert state['pnl_vehicle_filter']=='All' and state['dashboard_pnl_jump']
