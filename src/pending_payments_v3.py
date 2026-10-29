"""Refresh pending-only cards and compact numbered pagination."""
import importlib
from . import pending_payments
render_pending_payments = importlib.reload(pending_payments).render_pending_payments
