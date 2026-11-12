"""Guard expense dates and category transfers without silently changing user input."""
from .record_integrity import expense_summary

from .dtr_dates import parse_dtr_date
from .operational_dates import OPERATIONS_START


def apply_evidence_date(state, prefix, value):
    """A remembered date must not mask a different date on newly uploaded evidence."""
    if state.get(f'{prefix}_date_manual'):
        return
    date = parse_dtr_date(value)
    state[f'{prefix}_date'] = date if date and date >= OPERATIONS_START else None


def mark_expense_date_manual(prefix):
    import streamlit as st
    st.session_state[f'{prefix}_date_manual'] = True


def expense_category_increase(before, after):
    """Flag adding a category while retaining an existing amount; never guess a transfer."""
    old = before.get('categories', {})
    new = after.get('categories', {})
    retained = any(float(value or 0) > 0 and float(new.get(name) or 0) == float(value)
                   for name, value in old.items())
    added = any(float(value or 0) > 0 and not float(old.get(name) or 0)
                for name, value in new.items())
    previous = expense_summary({'dtr_data': before}).get('amount', 0)
    updated = expense_summary({'dtr_data': after}).get('amount', 0)
    return retained and added and updated > previous

