import pandas as pd
from streamlit.testing.v1 import AppTest
from src.report_grid import merge_visible_edits


def test_visible_edits_keep_original_row_identity_and_unseen_export_rows():
    original=pd.DataFrame({'Invoice':['A','B','C'],'Amount':[100,200,300],'Select':[True,False,True]})
    edited=original.loc[[1]].copy()
    edited.loc[1,'Amount']=225
    edited.loc[1,'Select']=True
    result=merge_visible_edits(original,edited)
    assert result['Amount'].tolist()==[100,225,300]
    assert result['Select'].tolist()==[True,True,True]
    assert original['Amount'].tolist()==[100,200,300]


def test_search_keeps_full_export_and_rekeys_editor_when_returning_to_query():
    app=AppTest.from_string('''
import streamlit as st
import pandas as pd
from src.report_grid import report_editor
search=st.text_input('Search',key='query')
frame=pd.DataFrame({'Invoice':['A','B'],'Amount':[100,200]})
result=report_editor(frame,'version1','test_report_grid',search)
st.json(result.to_dict('records'))
''').run()
    app.text_input[0].set_value('B').run()
    assert len(app.dataframe[0].value)==1
    assert len(app.session_state['_report_grid_test_report_grid']['frame'])==2
    generation=app.session_state['_report_grid_test_report_grid']['generation']
    app.text_input[0].set_value('no match').run()
    assert app.info and not app.exception
    app.text_input[0].set_value('B').run()
    assert app.session_state['_report_grid_test_report_grid']['generation']>generation
    assert len(app.session_state['_report_grid_test_report_grid']['frame'])==2
