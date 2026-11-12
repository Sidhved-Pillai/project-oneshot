"""Recover unfinished entry fields after a mobile WebSocket session is replaced."""
import datetime as dt
from pathlib import Path
import re

import streamlit as st
import streamlit.components.v1 as components

_bridge = components.declare_component('oneshot_entry_draft', path=str(Path(__file__).with_name('entry_draft_component')))
FIELD = re.compile(r'^(trip|expense)_(\d+)_([A-Za-z0-9_]+)$')
EXCLUDED = {'upload','camera','save','save_another','retry_autofill','invoice_evidence','camera_enabled'}


def generation(value):
    return value if type(value) is int and 0 <= value < 1000000 else 0


def clean_fields(values, generations):
    output = {}
    if not isinstance(values, dict):
        return output
    for key, value in values.items():
        if len(output) >= 300:
            break
        match = FIELD.fullmatch(str(key))
        if not match or int(match[2]) != generations.get(match[1], 0) or match[3] in EXCLUDED:
            continue
        if isinstance(value, (dt.date, dt.datetime)):
            value = value.isoformat()[:10]
        if isinstance(value, (list, tuple)) and len(value) <= 100:
            value = [item.isoformat()[:10] if isinstance(item, (dt.date, dt.datetime)) else item for item in value]
            if not all(item is None or isinstance(item, (str, bool, int, float)) for item in value):
                continue
        elif not (value is None or isinstance(value, (str, bool, int, float))):
            continue
        if isinstance(value, str) and len(value) > 10000:
            continue
        output[key] = value
    return output


def restore_fields(state, payload, prefer_current=True):
    if not isinstance(payload, dict):
        return
    generations = {}
    for kind, key in [('trip','new_entry_generation'), ('expense','direct_expense_generation')]:
        supplied = payload.get('generations')
        value = supplied.get(kind, 0) if isinstance(supplied, dict) else 0
        generations[kind] = generation(value)
        state.setdefault(key, generations[kind])
    for key, value in clean_fields(payload.get('values'), generations).items():
        field = FIELD.fullmatch(key)[3]
        if field == 'date':
            try:
                value = dt.date.fromisoformat(value) if value else None
            except (TypeError, ValueError):
                continue
        elif field.startswith('period_') and isinstance(value, list):
            try:
                value = tuple(dt.date.fromisoformat(item) for item in value)
            except (TypeError, ValueError):
                continue
        # Explicitly assign even an existing value so Streamlit sends set_value
        # to a fresh frontend after a reconnect, rather than showing its default.
        state[key] = state.get(key, value) if prefer_current else value


def recovered_draft(state, payload):
    """Fresh widget identities prevent a resumed frontend reusing empty defaults."""
    if not payload.get('values'):
        return payload
    supplied = payload.get('generations')
    old = {kind:generation(supplied.get(kind, 0)) if isinstance(supplied, dict) else 0
           for kind in ('trip','expense')}
    generations = {kind: max(old[kind], generation(state.get(key, 0))) + 1
                   for kind, key in [('trip','new_entry_generation'), ('expense','direct_expense_generation')]}
    values = {}
    for key, value in clean_fields(payload['values'], old).items():
        match = FIELD.fullmatch(key)
        values[f'{match[1]}_{generations[match[1]]}_{match[3]}'] = value
    state['new_entry_generation'] = generations['trip']
    state['direct_expense_generation'] = generations['expense']
    return {**payload, 'generations':generations, 'values':values}


def entry_draft_bridge(user):
    previous_user = st.session_state.get('_entry_draft_user')
    if previous_user is not None and previous_user != user:
        for key in list(st.session_state):
            if FIELD.fullmatch(key) or key in {'new_entry_generation','direct_expense_generation',
                                              '_entry_draft_ready','_entry_draft_boot'}:
                del st.session_state[key]
    st.session_state['_entry_draft_user'] = user
    ready = st.session_state.get('_entry_draft_ready', False)
    discard = st.session_state.get('_entry_draft_discard', False)
    generations = {'trip': st.session_state.get('new_entry_generation', 0),
                   'expense': st.session_state.get('direct_expense_generation', 0)}
    values = clean_fields(dict(st.session_state), generations)
    payload = _bridge(user=user, ready=ready, discard=discard, generations=generations, values=values,
                      key='entry_draft_bridge', default=None)
    if not isinstance(payload, dict) or payload.get('user') != user:
        st.stop()
    if discard:
        if not isinstance(payload, dict) or not payload.get('discarded'):
            st.stop()
        st.session_state.pop('_entry_draft_discard', None)
        payload = {**payload, 'values': {}, 'generations': {'trip':0, 'expense':0}}
    new_page = isinstance(payload, dict) and payload.get('boot') != st.session_state.get('_entry_draft_boot')
    if not ready or new_page:
        if not isinstance(payload, dict):
            st.stop()
        payload = recovered_draft(st.session_state, payload)
        restore_fields(st.session_state, payload, prefer_current=False)
        st.session_state['_entry_draft_boot'] = payload.get('boot')
        st.session_state['_entry_draft_ready'] = True
        if payload.get('values'):
            st.session_state['_entry_draft_restored_notice'] = True
            st.rerun()
    if st.session_state.pop('_entry_draft_restored_notice', False):
        st.info('Your unfinished entry fields were restored. Reattach any invoice files that are no longer shown.')
