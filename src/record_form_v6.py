"""Refresh company-review form submission on warm deployments."""
import importlib
from . import shyam_record_form

record_form = importlib.reload(shyam_record_form).record_form
