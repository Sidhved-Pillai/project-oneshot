"""Refresh the shared editor's customer-name field placement."""
import importlib
from . import shyam_record_form
record_form = importlib.reload(shyam_record_form).record_form
