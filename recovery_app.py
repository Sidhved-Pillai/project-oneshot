"""Independent Streamlit Cloud entry point for production recovery."""

# A separate entry-point path gives Community Cloud a fresh deployment while
# retaining the single tested application implementation in app.py.
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name("app.py")), run_name="__main__")
