"""Refresh Shyam's audited hard-copy receipt action on hot deployment."""
import importlib
from . import request_store
RequestStore = importlib.reload(request_store).RequestStore
