import ast
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_confirm_delete_commits_then_renders_close_without_full_rerun():
    source = Path('app.py').read_text()
    tree = ast.parse(source)
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == 'confirm_record_delete')
    dialog_source = ast.get_source_segment(source, function)
    app = AppTest.from_string('''
import streamlit as st
import streamlit.components.v1 as components
request_label = lambda record: record['request_number']
def soft_delete_record(record):
    st.session_state['deleted'] = record['request_number']
saved_record_script = lambda token: '<script></script>'
''' + dialog_source + '''
if st.button('Open delete dialog'):
    st.session_state['opened'] = True
if st.session_state.get('opened'):
    confirm_record_delete({'request_number': 'TEST-1'})
''').run()
    assert not app.exception
    next(button for button in app.button if button.label == 'Open delete dialog').click().run()
    assert not app.exception
    next(button for button in app.button if button.label == 'Confirm delete').click().run()
    assert not app.exception
    assert app.session_state['deleted'] == 'TEST-1'
    assert any('Deleted TEST-1.' in message.value for message in app.success)
