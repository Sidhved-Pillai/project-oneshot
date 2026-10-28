from streamlit.elements.lib.dialog import Dialog
from streamlit.delta_generator import context_dg_stack
from src.dialog_close import close_active_dialog


def test_close_sends_only_dialog_closed_state(monkeypatch):
    dialog = Dialog(None, None, None, None)
    events = []
    monkeypatch.setattr(Dialog, 'close', lambda self: events.append(self))
    token = context_dg_stack.set((object(), dialog))
    try:
        assert close_active_dialog()
        assert events == [dialog]
    finally:
        context_dg_stack.reset(token)


def test_no_active_dialog_uses_safe_fallback():
    token = context_dg_stack.set(())
    try:
        assert not close_active_dialog()
    finally:
        context_dg_stack.reset(token)
