"""Refresh the P&L dashboard with Sid-only duplicate review."""
import importlib
from . import pnl_dashboard
render_pnl_dashboard = importlib.reload(pnl_dashboard).render_pnl_dashboard
