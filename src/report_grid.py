"""Searchable native report editor, preserving all rows for export and saving."""
import hashlib
import streamlit as st


def merge_visible_edits(full, edited):
    result=full.copy(deep=True)
    for column in edited.columns:
        result.loc[edited.index,column]=edited[column].to_numpy()
    return result


def report_editor(frame, key, container_key, search, disabled=False, column_config=None, column_order=None):
    state_key='_report_grid_'+container_key
    state=st.session_state.get(state_key,{})
    full=state['frame'].copy(deep=True) if state.get('key')==key else frame.copy(deep=True)
    query=search.strip().casefold()
    mask=full.astype(str).apply(lambda col:col.str.casefold().str.contains(query,regex=False)).any(axis=1) if query else [True]*len(full)
    generation=state.get('generation',0)+(state.get('query')!=query)
    visible=full.loc[mask]
    if visible.empty:
        st.info('No rows match your search. Clear the search to show all report rows.')
    else:
        styled=visible
        if 'RTGS Status' in visible:
            styled=visible.style.map(lambda value:'background-color:#dcf7df;color:#17632b;font-weight:bold' if value=='RTGS Done' else 'background-color:#fff0d3;color:#9a4c08;font-weight:bold',subset=['RTGS Status'])
        with st.container(key=container_key):
            edited=st.data_editor(styled,hide_index=True,width='stretch',height=min(355,37+29*len(visible)),row_height=29,
                key=key+'_'+str(generation)+'_'+hashlib.sha256(query.encode()).hexdigest()[:10],disabled=disabled,
                column_config=column_config,column_order=column_order,num_rows='fixed')
        full=merge_visible_edits(full,edited)
    st.session_state[state_key]={'key':key,'frame':full,'query':query,'generation':generation}
    if query:st.caption(f'{len(visible)} matching row(s) · Search only changes the table view; downloads include the applied report and selections.')
    return full
