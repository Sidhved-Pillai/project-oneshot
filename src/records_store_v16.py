"""Reload Nitish's UPI reimbursement destination on hot deployment."""
import importlib
from . import request_store
RequestStore = importlib.reload(request_store).RequestStore
