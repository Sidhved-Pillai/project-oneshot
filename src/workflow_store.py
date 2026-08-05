"""Force a fresh storage interface after Streamlit Cloud hot deployments."""

import importlib

from . import request_store as _request_store


# A Git hot-pull may leave the previous module object in sys.modules. Reloading
# here is intentional: schema migrations and class methods must match app.py.
_request_store = importlib.reload(_request_store)
RequestStore = _request_store.RequestStore
