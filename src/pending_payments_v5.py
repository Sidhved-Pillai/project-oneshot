"""Refresh persistent balance and UPI summary widgets."""
import importlib
from . import pending_payments
render_pending_payments = importlib.reload(pending_payments).render_pending_payments
