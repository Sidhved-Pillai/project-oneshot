"""Load corrected native dashboard card buttons after hot deployment."""
import importlib
from . import pnl_dashboard
render_pnl_dashboard = importlib.reload(pnl_dashboard).render_pnl_dashboard
