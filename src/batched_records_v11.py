"""Refresh records filters with company review access rules."""
import importlib
from . import company_catalog, batched_records

importlib.reload(company_catalog)
_module = importlib.reload(batched_records)
render_filters = _module.render_filters
filter_identifiers = _module.filter_identifiers
