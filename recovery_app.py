"""Independent Streamlit Cloud entry point for production recovery."""

import streamlit as st

# Register the shared script as a page so Streamlit watches it for changes.
st.navigation([st.Page("app.py", title="Project OneShot", default=True)], position="hidden").run()
