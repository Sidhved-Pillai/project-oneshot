"""Exercise the real login form without starting database/report services."""

import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


def login_app():
    tree = ast.parse(Path("app.py").read_text())
    constants = {"SPECIAL_CODE_SALT", "SPECIAL_CODE_HASH", "MEMBER_CODE_HASHES", "SPECIAL_MEMBERS"}
    functions = {"clean_text", "verify_special_access_code", "identify_member", "require_authentication"}
    selected = [node for node in tree.body if
        (isinstance(node, ast.FunctionDef) and node.name in functions) or
        (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets))]
    source = """
import streamlit as st
import pandas as pd
import hashlib, hmac
secret = lambda name: None
valid_ashok_session_token = lambda value: False
issue_ashok_session_token = lambda: 'test-token'
""" + "\n".join(ast.unparse(node) for node in selected) + """
# Synthetic member code exercises the existing five-digit login path.
MEMBER_CODE_HASHES['Nitish'] = hashlib.pbkdf2_hmac('sha256', b'54321', SPECIAL_CODE_SALT, 600_000).hex()
require_authentication()
st.success('Authenticated: ' + st.session_state['authenticated_user'])
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


@pytest.mark.parametrize("code", ["101", "0000", "abcd", "1234567"])
def test_login_rejects_unknown_or_invalid_codes(code):
    app = login_app()
    app.text_input[0].set_value(code)
    app.button[0].click().run()
    assert not app.exception
    assert app.error[0].value == "Incorrect access code. Please try again."
