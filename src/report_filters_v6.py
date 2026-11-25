"""Refresh report filters with company review access rules."""
import importlib
from . import company_catalog, report_filters

importlib.reload(company_catalog)
render_report_filters = importlib.reload(report_filters).render_report_filters
