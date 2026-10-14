"""Reload calendar bounds during hot deployment."""
import importlib
from . import batched_records

render_filters = importlib.reload(batched_records).render_filters
