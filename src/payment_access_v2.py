"""Refresh reviewer permissions before loading UI and cached store interfaces."""
import importlib
from . import payment_access
PENDING_PAYMENT_USERS = importlib.reload(payment_access).PENDING_PAYMENT_USERS
