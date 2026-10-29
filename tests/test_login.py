"""Exercise the real login form without starting database/report services."""

import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


def login_app():
    tree = ast.parse(Path("app.py").read_text())
    constants = {"SPECIAL_CODE_SALT", "SPECIAL_CODE_HASH", "MEMBER_CODE_HASHES", "SPECIAL_MEMBERS"}
    functions = {"clean_text", "verify_special_access_code", "identify_member", "require_authentication", "logout"}
    selected = [node for node in tree.body if
        (isinstance(node, ast.FunctionDef) and node.name in functions) or
        (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets))]
    source = """
import streamlit as st
import pandas as pd
import hashlib, hmac
from src.member_sessions import signing_key, issue_member_session, restore_member_session
secret = lambda name: None
valid_ashok_session_token = lambda value: False
issue_ashok_session_token = lambda: 'test-token'
""" + "\n".join(ast.unparse(node) for node in selected) + """
# Synthetic member code exercises the existing five-digit login path.
MEMBER_CODE_HASHES['Nitish'] = hashlib.pbkdf2_hmac('sha256', b'54321', SPECIAL_CODE_SALT, 600_000).hex()
require_authentication()
st.success('Authenticated: ' + st.session_state['authenticated_user'])
st.button('Logout', on_click=logout)
"""
    return AppTest.from_string(source).run()


@pytest.mark.parametrize("code,member", [("1011", "Shyam"), ("54321", "Nitish")])
def test_login_form_accepts_authorized_four_and_five_digit_codes(code, member):
    app = login_app()
    app.text_input[0].set_value(code)
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state["authenticated_user"] == member
    assert app.success[0].value == "Authenticated: " + member
    token = app.query_params['member_session']
    refreshed = login_app()
    refreshed.query_params['member_session'] = token
    refreshed.run()
    assert not refreshed.exception
    assert refreshed.session_state['authenticated_user'] == member
    assert refreshed.session_state['is_special_member'] == (member == 'Shyam')


@pytest.mark.parametrize("code", ["101", "0000", "abcd", "1234567"])
def test_login_rejects_unknown_or_invalid_codes(code):
    app = login_app()
    app.text_input[0].set_value(code)
    app.button[0].click().run()
    assert not app.exception
    assert app.error[0].value == "Incorrect access code. Please try again."


def test_logout_clears_authentication_drafts_and_reconnect_tokens():
    app = login_app()
    app.text_input[0].set_value('1011')
    app.button[0].click().run()
    app.session_state['shyam_pending_receipts'] = {'REQ-TEST': True}
    app.query_params['ashok_session'] = 'legacy-token'
    next(button for button in app.button if button.label == 'Logout').click().run()
    assert not app.exception
    assert 'authenticated_user' not in app.session_state
    assert 'shyam_pending_receipts' not in app.session_state
    assert 'member_session' not in app.query_params
    assert 'ashok_session' not in app.query_params
    assert app.text_input[0].label == '4, 5 or 6-digit access code'
