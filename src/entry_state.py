def entry_state_prefix(generation):
    """Return a fresh Streamlit widget namespace for one trip entry."""
    return f"trip_{int(generation)}"


def expense_state_prefix(generation):
    """Return a fresh Streamlit widget namespace for one direct expense."""
    return f"expense_{int(generation)}"


def clear_entry_state(state):
    """Remove every field and upload belonging to the completed trip entry."""
    for key in list(state):
        if str(key).startswith("trip_"):
            del state[key]


def clear_expense_state(state):
    """Remove every field and upload belonging to a completed direct expense."""
    for key in list(state):
        if str(key).startswith("expense_"):
            del state[key]
