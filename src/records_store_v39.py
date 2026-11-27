"""Refresh the request store for guarded October trip cleanup."""
import importlib
from . import request_store

RequestStore = importlib.reload(request_store).RequestStore
