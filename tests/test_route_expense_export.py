import copy
import datetime as dt
from io import BytesIO
import json
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest
from src.route_expense_export import direct_expense_download_records, trip_route_amount
from src.records_export_v3 import export_records_excel
from src.pnl_report import branch_pnl_summary


def trip(**updates):
    return {'request_number':'TRIP-1','report_scope':'DTR','trip_date':dt.date(2026,11,5),
            'ownership_type':'Own','vehicle_number':'MH12AB1234','branch':'Wada','created_by':'Manish',
            'upi':1200,'revenue':20000,'amount':4500,'notes':'Trip expense',
            'invoice_number':'INV-12','dtr_data':{'LR No.':'LR-12','UPI':1200},**updates}


def filters(**updates):
    return {'start':dt.date(2026,11,1),'end':dt.date(2026,11,30),'vehicle':'All','heading':'All','amount':'All',**updates}


def test_legacy_and_trip_route_expenses_share_heading_and_export_amount_without_mutation():
    old={'request_number':'EXP-1','report_scope':'Expense','trip_date':dt.date(2026,11,4),
         'created_by':'Nikhat','branch':'Wada','amount':200,'expense_type':'Route expense',
         'dtr_data':{'categories':{'Route expense':200}}}
    own=trip()
    outside=trip(request_number='OUT-1',ownership_type='Outside',upi=9000)
    original=copy.deepcopy([old,own,outside])
    before=branch_pnl_summary([own,outside],[{**old,'categories':{'Route expense':200}}])
    rows=direct_expense_download_records([old],[old,own,outside],filters())
    assert [r['request_number'] for r in rows]==['EXP-1','TRIP-1']
    assert rows[1]['report_scope']=='DTR' and rows[1]['amount']==1200
    sheet=load_workbook(BytesIO(export_records_excel(rows,direct_expenses=True))).active
    records=[dict(zip([c.value for c in sheet[1]],values)) for values in sheet.iter_rows(min_row=2,values_only=True)]
    assert [r['Expense Heading'] for r in records]==['Route expense','Route expense']
    assert sum(r['Amount'] for r in records)==1400
    assert records[1]['Vehicle Number']=='MH12AB1234'
    assert records[1]['Total Advance']==1200 and records[1]['Payment Mode']=='UPI'
    assert [old,own,outside]==original
    assert branch_pnl_summary([own,outside],[{**old,'categories':{'Route expense':200}}])==before


def test_all_export_filters_apply_to_trip_linked_costs_and_route_only_download_works():
    own=trip()
    assert len(direct_expense_download_records([], [own], filters(heading='Route expense',amount=1200)))==1
    for extra in ({'heading':'Salary'},{'amount':4500},{'vehicle':'MH00NONE'},
                  {'start':dt.date(2026,11,6)},{'end':dt.date(2026,11,4)},
                  {'lr_number':'missing'},{'invoice_number':'missing'}):
        assert direct_expense_download_records([], [own], filters(**extra))==[]
    assert direct_expense_download_records([], [trip(source_filename='bill.jpg')], filters(),True)==[]
    assert len(direct_expense_download_records([], [own,own], filters(lr_number='lr-',invoice_number='inv-')))==1


def test_route_column_on_trip_export_and_scalar_overrides_stale_dtr():
    sheet=load_workbook(BytesIO(export_records_excel([trip(upi=700)]))).active
    values=dict(zip([c.value for c in sheet[1]],[c.value for c in sheet[2]]))
    assert values['Route expense']==700
    assert trip_route_amount(trip(upi=0))==0
    assert trip_route_amount(trip(upi=None,dtr_data=json.dumps({'UPI':500})))==500
    for updates in ({'ownership_type':'Outside'},{'upi':float('nan')},{'upi':-1},{'status':'Cancelled'},{'is_archived':True}):
        assert trip_route_amount(trip(**updates))==0


def test_route_heading_and_amount_are_available_without_old_direct_expenses():
    app=AppTest.from_string('''
import datetime as dt
import streamlit as st
from src.batched_records_v7 import render_filters
st.session_state['applied_records_filters_Sid']={'record_type':'Direct Expenses'}
render_filters([{'request_number':'one','report_scope':'DTR','ownership_type':'Own','upi':750,
    'trip_date':dt.date(2026,11,5),'vehicle_number':'MH12AB1234','dtr_data':{}}],'Sid',dt.date(2026,11,12))
''').run()
    assert not app.exception
    heading=next(w for w in app.selectbox if w.label=='Heading')
    assert 'Route expense' in heading.options
    amount=next(w for w in app.selectbox if w.label=='By Amount')
    assert amount.options==['All']


def test_direct_expense_forms_hide_route_and_keep_existing_category_widget_ids():
    import ast
    from pathlib import Path
    tree=ast.parse(Path('app.py').read_text())
    wanted={'PAYMENT_FIELDS','BRANCHES','STANDARD_DIRECT_EXPENSE_COLUMNS','NIKHAT_DIRECT_EXPENSE_COLUMNS',
            'MANISH_DIRECT_EXPENSE_COLUMNS','ALL_DIRECT_EXPENSE_COLUMNS'}
    imports=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))]
    constants=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in wanted for t in n.targets)]
    definitions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and (not n.decorator_list or n.name=='render_direct_expenses')]
    source='\n'.join(ast.unparse(n) for n in imports+constants+definitions)
    for user in ('Nikhat','Ajit','Manish'):
        app=AppTest.from_string(source+f'''\ncurrent_user={user!r}
can_use_direct_expenses=True
normalization_rows=[]
business_memory={{}}
saved_expense_notice=None
allowed_entry_branches=BRANCHES
render_direct_expenses()
''').run()
        assert not app.exception
        assert not any(w.label=='Route expense (₹)' for w in app.number_input)
        if user != 'Manish':
            salary=next(w for w in app.number_input if w.label=='Salary (₹)')
            assert salary.key.endswith('_category_2')
