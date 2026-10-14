import ast
import datetime as dt
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest
from src.records_store_v15 import RequestStore
from src.record_filters_v2 import filter_record_type, RECORD_TYPES


def test_both_returns_all_records_without_modifying_source():
    rows=[{'report_scope':'Both'}, {'report_scope':'Expense'}]
    assert 'Both' in RECORD_TYPES
    assert filter_record_type(rows,'Both') == rows
    assert filter_record_type(rows,'Both') is not rows


def test_legacy_repair_preserves_identity_evidence_payments_and_is_idempotent(tmp_path):
    store=RequestStore(f"sqlite:///{tmp_path / 'years.db'}")
    number=store.create({'trip_date':dt.date(2016,10,12), 'vehicle_number':'MH1234',
        'created_by':'Vijay','revenue':1234,'rtgs_advance':500,'rtgs_done':True,
        'source_image':b'invoice','invoice_number':'INV2016',
        'dtr_data':{'Date':'2016-10-12','Revenue':1234},
        'rtgs_data':{'BENE_ACC_NO':'001234','REMARK':'1234 Pune to Mumbai 12 10 2016 TA'}})
    leap=store.create({'trip_date':dt.date(2024,2,29),'vehicle_number':'leap'})
    result=store.repair_legacy_years()
    assert result['repaired']==[number] and result['skipped']==[leap]
    row=store.get(number)
    assert row['trip_date']==dt.date(2026,10,12)
    assert row['rtgs_done'] is True and row['rtgs_advance']==500
    assert row['invoice_number']=='INV2016'
    assert store.get_evidence(number)['source_image']==b'invoice'
    assert json.loads(row['rtgs_data'])['BENE_ACC_NO']=='001234'
    assert '12 10 2026' in json.loads(row['rtgs_data'])['REMARK']
    assert store.repair_legacy_years()['repaired']==[]


def dialog_app():
    tree=ast.parse(Path('app.py').read_text())
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'finish_trip_save','confirm_trip_month'}]
    source='''
import streamlit as st
import datetime as dt
current_user='Nitish'
st.session_state.setdefault('_saved',[])
class Store:
    def list(self,**kwargs):return []
    def create(self,payload):
        st.session_state['_saved'].append(payload)
        return 'REQ1'
store=Store()
user_invoice_duplicates=lambda *args:[]
user_lr_duplicates=lambda *args:[]
audit_action=lambda *args:None
request_label=lambda *args:'Trip'
'''+ '\n'.join(ast.unparse(n) for n in selected)+'''
st.text_input('Draft',key='draft')
if st.button('Save'):
    st.session_state['_dialog_open'] = True
if st.session_state.get('_dialog_open'):
    confirm_trip_month({'trip_date':dt.date(2026,6,12),'created_by':'Nitish','dtr_data':{}},0)
'''
    return AppTest.from_string(source).run()


def test_no_keeps_draft_and_yes_saves_once():
    app=dialog_app()
    app.text_input[0].set_value('Keep my entry').run()
    next(b for b in app.button if b.label=='Save').click().run()
    assert any('June 2026' in item.value for item in app.markdown)
    next(b for b in app.button if b.label=='No').click().run()
    assert not app.exception and len(app.session_state['_saved'])==0
    assert app.text_input[0].value=='Keep my entry'
    next(b for b in app.button if b.label=='Save').click().run()
    next(b for b in app.button if b.label=='Yes').click().run()
    assert not app.exception and len(app.session_state['_saved'])==1
    assert app.session_state['_saved'][0]['trip_date']==dt.date(2026,6,12)
