"""Current record-store interface for Streamlit Cloud hot deployments."""

import importlib

from . import request_store as _request_store


_request_store = importlib.reload(_request_store)
RequestStore = _request_store.RequestStore
