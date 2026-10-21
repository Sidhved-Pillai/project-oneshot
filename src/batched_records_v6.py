"""Refresh stable draft widget keys for repeated Apply Filters submissions."""
import importlib
from . import batched_records
_filters = importlib.reload(batched_records)
render_filters = _filters.render_filters
filter_identifiers = _filters.filter_identifiers
