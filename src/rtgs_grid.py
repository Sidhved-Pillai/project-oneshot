"""RTGS table with accessible, single-click status badges."""
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

_grid = components.declare_component('oneshot_rtgs_status_grid', path=str(Path(__file__).with_name('rtgs_grid_component')))


def apply_grid_event(frame, event, revision, editable):
    """Accept only allowed cell edits from the currently displayed report."""
    result = frame.copy(deep=True)
    if not isinstance(event, dict):
        return result
    for patch in event.get('patches', [])[:len(frame)*8]:
        if not isinstance(patch, dict):
            continue
        index, column, value = patch.get('row'), patch.get('column'), patch.get('value')
        record = patch.get('record')
        if record is not None:
            # Status saves reorder rows and change the report revision. Resolve
            # in-flight clicks by stable identity, never by the old row index.
            matches = [i for i, item in enumerate(frame.get('Record', [])) if item == record]
            if len(matches) != 1:
                continue
            index = matches[0]
        elif event.get('revision') != revision:
            continue
        if not isinstance(index, int) or not 0 <= index < len(frame) or column not in editable or column != 'RTGS Status':
            continue
        if column == 'RTGS Status' and value not in ('Pending', 'RTGS Done'):
            continue
        result.iat[index, result.columns.get_loc(column)] = value
    return result


def rtgs_editor(frame, key, search, disabled, column_order):
    editable = [c for c in ('RTGS Status',) if c in frame.columns and disabled is not True and (disabled is False or c not in disabled)]
    state_key = '_rtgs_badge_table'
    state = st.session_state.get(state_key, {})
    full = state['frame'].copy(deep=True) if state.get('revision') == key else frame.copy(deep=True)
    # JSON conversion preserves bank account strings and excludes NaN values.
    import json
    rows = json.loads(full.to_json(orient='records'))
    event = _grid(rows=rows, columns=column_order or list(full.columns), editable=editable,
                  revision=key, search=search, key='rtgs_badge_grid', default=None)
    if isinstance(event, dict) and event.get('nonce') != state.get('nonce'):
        full = apply_grid_event(full, event, key, editable)
    st.session_state[state_key] = {'revision':key, 'frame':full, 'nonce':event.get('nonce') if isinstance(event, dict) else None}
    return full
