"""Keep the mobile entry visible during Streamlit's brief resume updates.

Do not override disabled controls, reconnect errors, or save progress indicators.
The server retains disconnected sessions separately via disconnectedSessionTTL.
"""
import streamlit as st


def render_mobile_resume_styles():
    st.markdown('''<style>
    @media (max-width:750px), (hover:none) and (pointer:coarse){
      [data-testid="stElementContainer"][data-stale="true"]{
        opacity:1!important;
        transition:none!important;
      }
    }
    </style>''', unsafe_allow_html=True)
