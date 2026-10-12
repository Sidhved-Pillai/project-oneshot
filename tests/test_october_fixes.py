import ast
import datetime as dt
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.invoice_numbers_v2 import invoice_identifier_tokens, user_invoice_duplicates
from src.business_memory_v2 import build_business_memory, recall
from src.current_pnl_report_v2 import branch_pnl_summary, branch_vehicle_pnl_summary, vehicle_number_pnl_summary
from src.member_sessions import issue_member_session, restore_member_session


def test_gk_full_invoice_identity_not_shared_prefix_or_year():
    rows = [{'created_by': 'Sid', 'status': 'Verified', 'invoice_number': 'GST/GST/0885/26-27'}]
    assert not user_invoice_duplicates(rows, 'Sid', 'GST/GST/1087/26-27')
    assert not user_invoice_duplicates(rows, 'Sid', 'GST/GST/123/26-27')
    assert user_invoice_duplicates(rows, 'Sid', 'gst / gst / 0885 / 26-27') == rows
    assert not user_invoice_duplicates(rows, 'Sid', 'GST/GST/0885/27-28')
    assert invoice_identifier_tokens('GST/GST/0885/26-27 / GST/GST/1087/26-27') == {'gstgst08852627', 'gstgst10872627'}
    assert user_invoice_duplicates(rows, 'Sid', 'INV-OTHER / GST/GST/0885/26-27') == rows


def test_pnl_expense_branch_case_merges_without_losing_amounts():
    trips = [{'branch': 'Andheri', 'vehicle_number': 'MH1234', 'ownership_type': 'Outside',
              'revenue': 10000, 'transporter_freight': 7000}]
    expenses = [{'branch': '  andheri  ', 'vehicle_number': 'MH1234',
                 'categories': {'Rent': 2000}, 'ownership_type': 'Outside'}]
    rows = branch_pnl_summary(trips, expenses)
    assert [r['Branch'] for r in rows] == ['Andheri', 'Total']
    assert rows[0]['Rent'] == 2000 and rows[0]['Total Revenue'] == 10000
    assert all('andheri' not in r.get('Branch', '') for r in branch_vehicle_pnl_summary(trips, expenses, 'Outside'))
    assert all(r.get('Branch') in ('Andheri', 'Total', None, '') for r in vehicle_number_pnl_summary(trips, expenses))


def profile_rows():
    return [dict(id=i, status='Verified', report_scope='Both', transporter_name='Shivshambho Transport',
                 beneficiary_name=name, updated_at=f'2026-10-{i:02d}', trip_date=dt.date(2026,9,1),
                 rtgs_data=json.dumps({'BENE_ACC_NO': account, 'BENE_IFSC': ifsc}))
            for i, name, account, ifsc in [(1,'Priyanka','00111','BANK001'),
                (2,'Priyanka','00111','BANK001'), (3,'Rahul','00222','BANK002')]]


def test_latest_saved_profile_is_coherent_and_keeps_older_beneficiaries():
    memory = build_business_memory(profile_rows())
    latest = recall(memory, 'transporters', 'Shivshambho Transport')
    assert latest['beneficiary_name'][0] == 'Rahul'
    assert latest['account_number'][0] == '00222' and latest['ifsc'][0] == 'BANK002'
    associated = recall(memory, 'transporter_beneficiaries', 'Shivshambho Transport')
    assert set(associated) == {'PRIYANKA', 'RAHUL'}
    assert associated['PRIYANKA']['account_number'][0] == '00111'


def test_real_beneficiary_dropdown_switches_banks_and_accepts_new_name():
    tree = ast.parse(Path('app.py').read_text())
    names = {'clean_text', 'apply_saved_beneficiary_profile', 'beneficiary_selector',
             'apply_saved_transporter_profile', 'transporter_selector'}
    source = '''
import streamlit as st
import pandas as pd
import re
from src.business_memory_v2 import build_business_memory, recall
from src.transporter_profiles import canonical_transporter_name
'''
    source += f"business_memory = build_business_memory({profile_rows()!r})\n".replace('datetime.date', 'dt.date')
    source = 'import datetime as dt\n' + source
    source += '\n'.join(ast.unparse(n) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names)
    source += '''
transporter = transporter_selector('test', st, business_memory, 'Sid')
beneficiary_selector('test', st, business_memory, transporter)
st.text_input('Account', key='test_beneficiary_account_number')
st.text_input('IFSC', key='test_beneficiary_ifsc_code')
def enter_new_beneficiary():
    st.session_state['test_beneficiary_name'] = 'New beneficiary'
    apply_saved_beneficiary_profile('test')
st.button('Enter new beneficiary', on_click=enter_new_beneficiary)
'''
    app = AppTest.from_string(source).run()
    app.selectbox[0].select('Shivshambho Transport').run()
    assert not app.exception
    assert app.selectbox[0].value == 'Shivshambho Transport'
    assert app.selectbox[1].value == 'Rahul'
    assert app.text_input[0].value == '00222'
    app.selectbox[1].select('Priyanka').run()
    assert not app.exception
    assert app.text_input[0].value == '00111'
    app.selectbox[1].select('Rahul').run()
    assert not app.exception
    assert app.text_input[0].value == '00222' and app.text_input[1].value == 'BANK002'
    app.run()
    assert app.selectbox[0].value == 'Shivshambho Transport'
    assert app.selectbox[1].value == 'Rahul'
    # AppTest cannot serialize accept_new_options values absent from options;
    # exercise the same server state/callback transition via a test-only button.
    app.button[0].click().run()
    assert not app.exception
    assert app.selectbox[0].value == 'Shivshambho Transport'
    assert app.selectbox[1].value == 'New beneficiary'
    assert app.text_input[0].value == '' and app.text_input[1].value == ''


@pytest.mark.parametrize('member', ['Ashok','Nitish','Sid','Nikhat','Vijay','Shyam'])
def test_refresh_token_is_member_bound_expiring_and_code_bound(member):
    codes = {member: 'codehash', 'Other': 'otherhash'}
    token = issue_member_session(member, b'private-server-key', codes, now=100)
    assert restore_member_session(token, b'private-server-key', codes, now=101) == member
    assert restore_member_session(token, b'wrong-server-key', codes, now=101) is None
    assert restore_member_session(token, b'private-server-key', {member:'changed'}, now=101) is None
    assert restore_member_session(token, b'private-server-key', codes, now=1000000) is None
    assert restore_member_session(token + 'tampered', b'private-server-key', codes, now=101) is None
