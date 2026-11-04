"""Refresh branch-head grouping for Billtee payments."""
import importlib
from . import pending_payments
render_pending_payments = importlib.reload(pending_payments).render_pending_payments
