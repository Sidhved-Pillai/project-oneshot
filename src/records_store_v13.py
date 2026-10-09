"""Refresh the store and additive UPI schema during a hot deployment."""
import importlib
from . import request_store

RequestStore = importlib.reload(request_store).RequestStore
