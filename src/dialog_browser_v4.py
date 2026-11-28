"""Refresh edit confirmation dialog closing on warm Streamlit deployments."""
import importlib
from . import dialog_browser

_module = importlib.reload(dialog_browser)
explicit_close_script = _module.explicit_close_script
saved_record_script = _module.saved_record_script
close_edited_record_script = _module.close_edited_record_script
