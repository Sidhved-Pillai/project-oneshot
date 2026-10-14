"""Reload Both record filtering and 2026 calendar bounds."""
import importlib
from . import batched_records
render_filters = importlib.reload(batched_records).render_filters
