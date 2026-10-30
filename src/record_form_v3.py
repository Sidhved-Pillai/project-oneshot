"""Refresh the shared editor's driver-name field placement."""
import importlib
from . import shyam_record_form
record_form = importlib.reload(shyam_record_form).record_form
