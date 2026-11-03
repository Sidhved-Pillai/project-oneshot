"""Refresh Sid's responsive desktop/mobile preview after deployment."""
import importlib
from . import sid_entry_design
_design = importlib.reload(sid_entry_design)
render_sid_styles = _design.render_sid_styles
render_sid_header = _design.render_sid_header
section_heading = _design.section_heading
PATHS = _design.PATHS
