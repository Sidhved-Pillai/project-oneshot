"""Refresh canonical branch-head payment groups."""
import importlib
from . import pending_payments
render_pending_payments = importlib.reload(pending_payments).render_pending_payments
