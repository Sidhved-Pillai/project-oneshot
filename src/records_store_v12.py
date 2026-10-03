"""Refresh the store interface when Streamlit deploys balance payments."""
import importlib
from . import request_store

RequestStore = importlib.reload(request_store).RequestStore
