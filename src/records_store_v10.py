"""Current record-store interface for Streamlit Cloud hot deployments."""

import importlib

from . import request_store as _request_store


# This versioned module name forces Streamlit's long-lived Python process to
# import the current RequestStore class after a Git hot update.
_request_store = importlib.reload(_request_store)
RequestStore = _request_store.RequestStore
