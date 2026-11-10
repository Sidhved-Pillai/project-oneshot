import importlib
from . import request_store
RequestStore = importlib.reload(request_store).RequestStore
