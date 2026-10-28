import ast
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_fragment_edit_control_opens_dialog():
    tree = ast.parse(Path('app.py').read_text())
    control = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == 'record_edit_control')
    app = AppTest.from_string('''
import streamlit as st
st.session_state['dashboard_reads'] = st.session_state.get('dashboard_reads', 0) + 1
@st.dialog('Test record editor')
def view_record(record):
    st.write('Opened ' + record['request_number'])
''' + ast.unparse(control) + "\nrecord_edit_control({'request_number':'TEST-1'})\n").run()
    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
    # AppTest starts a full script runner per run; browser fragment routing is
    # supplied by Streamlit. Verify registration and the nested dialog here.
    assert any(isinstance(node, ast.Attribute) and node.attr == 'fragment'
               for node in control.decorator_list)
    assert any('Opened TEST-1' in item.value for item in app.markdown)
