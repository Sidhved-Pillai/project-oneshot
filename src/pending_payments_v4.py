"""Refresh fragment-based review and compact pagination controls."""
import importlib
from . import pending_payments
render_pending_payments = importlib.reload(pending_payments).render_pending_payments
