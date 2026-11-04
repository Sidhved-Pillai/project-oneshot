"""Refresh store authorization after adding Nikhat as a payment reviewer."""
import importlib
from . import request_store
RequestStore = importlib.reload(request_store).RequestStore
