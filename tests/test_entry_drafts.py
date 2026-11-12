import datetime as dt
from src.entry_drafts import clean_fields, restore_fields


def test_recovery_keeps_account_text_dates_optional_numbers_and_invoice_list():
    state={}
    restore_fields(state,{'generations':{'trip':3,'expense':2},'values':{
        'trip_3_company_name':'A company','trip_3_diesel_advance':123.45,
        'trip_3_beneficiary_account_number':'001234','trip_3_invoice_numbers':['INV1','INV2'],
        'trip_3_date':'2026-11-12','expense_2_period_insurance':['2026-10-01','2026-10-31'],
        'authenticated_user':'Sid','trip_0_company_name':'old','trip_3_upload':'file'}})
    assert state['new_entry_generation']==3 and state['direct_expense_generation']==2
    assert state['trip_3_beneficiary_account_number']=='001234'
    assert state['trip_3_date']==dt.date(2026,11,12)
    assert state['trip_3_diesel_advance']==123.45
    assert state['trip_3_invoice_numbers']==['INV1','INV2']
    assert state['expense_2_period_insurance']==(dt.date(2026,10,1),dt.date(2026,10,31))
    assert not {'authenticated_user','trip_0_company_name','trip_3_upload'} & state.keys()


def test_draft_never_overwrites_live_session_or_includes_file_bytes():
    state={'trip_0_company_name':'Live value'}
    restore_fields(state,{'values':{'trip_0_company_name':'Old value'}})
    assert state['trip_0_company_name']=='Live value'
    assert clean_fields({'trip_0_upload':b'file','trip_0_camera':b'photo',
                         'trip_0_company_name':'Good','trip_1_company_name':'Saved',
                         'trip_0_date':dt.date(2026,11,12)}, {'trip':0,'expense':0})=={
                             'trip_0_company_name':'Good','trip_0_date':'2026-11-12'}


def test_recovered_draft_uses_new_widget_keys_without_reusing_saved_form_generation():
    from src.entry_drafts import recovered_draft
    state={'new_entry_generation':4,'direct_expense_generation':1}
    payload={'generations':{'trip':4,'expense':1},'values':{
        'trip_4_company_name':'Draft company','expense_1_category_2':500}}
    migrated=recovered_draft(state,payload)
    restore_fields(state,migrated,prefer_current=False)
    assert state['new_entry_generation']==5 and state['direct_expense_generation']==2
    assert state['trip_5_company_name']=='Draft company'
    assert state['expense_2_category_2']==500
    assert 'trip_4_company_name' not in state
