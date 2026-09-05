def entry_state_prefix(generation):
    """Return a fresh Streamlit widget namespace for one trip entry."""
    return f"trip_{int(generation)}"


def clear_entry_state(state):
    """Remove every field and upload belonging to the completed trip entry."""
    for key in list(state):
        if str(key).startswith("trip_"):
            del state[key]

