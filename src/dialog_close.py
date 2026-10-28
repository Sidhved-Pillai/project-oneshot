"""Close the active Streamlit 1.50 dialog without rerunning the application.

Streamlit's public close example uses a full app rerun. The pinned version's
dialog object can instead send just its closed state to the browser.
"""
from streamlit.delta_generator import context_dg_stack
from streamlit.elements.lib.dialog import Dialog


def close_active_dialog():
    for container in reversed(context_dg_stack.get()):
        if isinstance(container, Dialog):
            container.close()
            return True
    return False
