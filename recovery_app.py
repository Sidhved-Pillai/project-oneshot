"""Independent Streamlit Cloud entry point for production recovery."""

# A separate entry-point path gives Community Cloud a fresh deployment while
# retaining the single tested application implementation in app.py.
from app import *  # noqa: F401,F403
