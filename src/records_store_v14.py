"""Load the fresh, consolidated dashboard reader during hot deployment."""
import importlib
from . import request_store

RequestStore = importlib.reload(request_store).RequestStore
