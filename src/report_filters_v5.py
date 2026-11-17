"""Refresh shared report dates and immediate report-format switching."""
import importlib
from . import report_filters
render_report_filters=importlib.reload(report_filters).render_report_filters
