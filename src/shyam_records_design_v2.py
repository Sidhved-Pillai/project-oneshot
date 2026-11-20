"""Reload the Records presentation on a warm Streamlit deployment."""
import importlib
from . import shyam_records_design
_module = importlib.reload(shyam_records_design)
styles = _module.styles
heading = _module.heading
leaderboard = _module.leaderboard
TRUCK = _module.TRUCK
