"""Refresh the on-demand invoice preview during hot deployment."""
import importlib
from . import shyam_record_form

record_form = importlib.reload(shyam_record_form).record_form
