"""Refresh reference-design payment cards on hot deployment."""
import importlib
from . import pending_payments
render_pending_payments = importlib.reload(pending_payments).render_pending_payments
