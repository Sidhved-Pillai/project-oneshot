import datetime as dt
import json
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import select, func

from src.balance_bill import totals, export_bill, render_bill_html, words, payment_status
from src.request_store import RequestStore, balance_bills
from src.balance_payments import BALANCE_PREFIX


def trip(store, invoice='TEST1', account='001234', name='Example Transport'):
    return store.create({'created_by':'Nitish','report_scope':'Both','trip_date':dt.date(2026,10,20),
        'branch':'Pune','vehicle_number':'TEST1234','vehicle_type':'12 MT','ownership_type':'Outside',
        'transporter_name':name,'beneficiary_name':'Example Payee','transporter_freight':10000,
        'revenue':12000,'rtgs_advance':8900,'total_advance':9000,'balance_amount':1000,
        'invoice_number':invoice,'from_location':'Kamshet','to_location':'Pune',
        'dtr_data':{'Invoice No.':invoice,'LR No.':'LR1','Customer Name':'Example Customer','Billtee':100,'LR Status':'Received'},
        'rtgs_data':{'BNF_NAME':'Example Payee','BENE_ACC_NO':account,'BENE_IFSC':'TEST0000001'}})


def test_selected_trips_create_persistent_bill_once_and_track_actual_payment(tmp_path):
    store=RequestStore(f'sqlite:///{tmp_path / "bills.db"}')
    first,second,unselected=[trip(store, invoice) for invoice in ['1, 2','3','4']]
    selected={n:store.get(n)['updated_at'] for n in [first,second]}
    assert store.send_pending_payments(selected,'balance','Sid') == 2
    summaries=store.list_balance_bills('Shyam')
    assert len(summaries)==1 and summaries[0]['trip_count']==2
    bill=store.get_balance_bill(summaries[0]['id'],'Ajit')
    assert {r['request_number'] for r in bill['rows']} == {first,second}
    assert unselected not in store.list_balance_payments()
    assert totals(bill)['grand_total']==2000
    assert totals(bill)['Balance Amt.']==2200 and totals(bill)['billtee']==200
    assert totals(bill)['adjustment']==0
    assert 'pending' in payment_status(bill)
    store.update(first,{'transporter_freight':99999,'invoice_number':'CHANGED'})
    saved=store.get_balance_bill(summaries[0]['id'],'Sid')
    assert saved['rows'][0]['Invoice No.']=='1, 2'
    assert saved['rows'][0]['Freight Amt.']=='10000.00'
    assert store.send_pending_payments({n:store.get(n)['updated_at'] for n in [first,second]},'balance','Sid')==0
    assert len(store.list_balance_bills('Sid'))==1
    store.mark_rtgs_done([BALANCE_PREFIX+first, BALANCE_PREFIX+second])
    assert payment_status(store.get_balance_bill(summaries[0]['id'],'Sid'))=='Paid / RTGS Done'
    store.mark_rtgs_done([BALANCE_PREFIX+second],False)
    assert 'Partly paid' in payment_status(store.get_balance_bill(summaries[0]['id'],'Sid'))


def test_atomic_batch_failure_creates_no_bill_or_payment_and_accounts_split(tmp_path):
    store=RequestStore(f'sqlite:///{tmp_path / "atomic.db"}')
    first,second=trip(store),trip(store,account='009999')
    with pytest.raises(ValueError):
        store.send_pending_payments({first:store.get(first)['updated_at'],second:'stale'},'balance','Sid')
    assert store.list_balance_payments()=={} and store.list_balance_bills('Sid')==[]
    store.send_pending_payments({n:store.get(n)['updated_at'] for n in [first,second]},'balance','Sid')
    assert len(store.list_balance_bills('Sid'))==2
    for row in store.list_balance_bills('Sid'):
        assert row['trip_count']==1
    for operation in (lambda:store.list_balance_bills('Nitish'), lambda:store.get_balance_bill(1,'Nitish')):
        with pytest.raises(ValueError):operation()


def test_printable_and_excel_match_snapshot_and_keep_bank_account_text(tmp_path):
    store=RequestStore(f'sqlite:///{tmp_path / "export.db"}')
    number=trip(store, invoice='GST/GST/0885/26-27, TEST2',name='<script>Example</script>')
    store.send_pending_payments({number:store.get(number)['updated_at']},'balance','Sid')
    bill=store.get_balance_bill(store.list_balance_bills('Sid')[0]['id'],'Sid')
    content=render_bill_html(bill)
    assert '<script>Example</script>' not in content and '&lt;script&gt;' in content
    assert 'GST/GST/0885/26-27, TEST2' in content
    assert 'pending' in content
    book=load_workbook(BytesIO(export_bill(bill)))
    ws=book.active
    assert ws['G8'].value=='GST/GST/0885/26-27, TEST2'
    assert ws['J8'].value==10000 and ws['Q8'].value==1100
    assert any(cell.value=='A/c No.: 001234' for row in ws for cell in row)
    grand = [cell for row in ws for cell in row if cell.value=='Grand Total:'][0]
    assert ws.cell(grand.row,17).value==1000
    assert ws.page_setup.orientation=='landscape'
    assert words(10700)=='Ten Thousand Seven Hundred Rupees Only'


def test_bill_history_remains_available_after_all_pending_trips_sent(tmp_path):
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_string(f'''
import streamlit as st
from src.request_store import RequestStore
from src.pending_payments import render_pending_payments
from tests.test_balance_bills import trip
store=RequestStore({'sqlite:///' + str(tmp_path / 'ui.db')!r})
if 'fixture_ready' not in st.session_state:
    number=trip(store)
    store.send_pending_payments({{number:store.get(number)['updated_at']}},'balance','Sid')
    st.session_state['fixture_ready']=True
trips,balances,upi,_=store.dashboard_snapshot()
render_pending_payments('Sid',trips,balances,upi,store)
''').run()
    assert not app.exception
    assert any('No payments match' in info.value for info in app.info)
    next(button for button in app.button if button.key=='pending_bill_history').click().run()
    assert not app.exception
    assert any(w.label=='Bill' for w in app.selectbox)


def test_upi_submissions_do_not_create_transporter_bills(tmp_path):
    from sqlalchemy import insert
    from src.request_store import upi_reimbursement_profiles
    store=RequestStore(f'sqlite:///{tmp_path / "upi-only.db"}')
    number=trip(store)
    store.update(number,{'upi':500})
    with store.engine.begin() as conn:
        conn.execute(insert(upi_reimbursement_profiles).values(user_name='Nitish',beneficiary_data=json.dumps(
            {'BNF_NAME':'Example Staff','BENE_ACC_NO':'000123','BENE_IFSC':'TEST0000001'})))
    assert store.send_pending_payments({number:store.get(number)['updated_at']},'upi','Sid')==1
    assert store.list_balance_bills('Sid')==[]
