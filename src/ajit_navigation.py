"""Ajit's desktop header adapts without changing the shared mobile layout."""
import streamlit as st


def render_ajit_navigation_styles():
    st.markdown('''<style>
    @media(min-width:751px){
      .stTabs [data-baseweb="tab-list"]{overflow-x:auto!important;overflow-y:hidden!important;scrollbar-width:thin;max-width:calc(100vw - 505px - 3.7vw)!important}
    }
    @media(min-width:1401px) and (max-width:1700px){
      .stTabs [data-baseweb="tab-list"]{gap:6px!important}
      [data-testid="stTabs"] [data-testid="stTab"]{font-size:11px!important;padding:7px 8px!important;gap:5px!important}
      [data-testid="stTabs"] [data-testid="stTab"]:before{font-size:18px!important}
    }
    @media(min-width:751px) and (max-width:1400px){
      .sid-topbar{height:116px!important}
      .block-container{padding-top:145px!important}
      .stTabs [data-baseweb="tab-list"]{top:65px!important;left:3.7%!important;right:3.7%!important;max-width:92.6vw!important;height:43px!important;gap:8px!important}
      [data-testid="stTabs"] [data-testid="stTab"]{font-size:11px!important;padding:7px 8px!important}
    }
    </style>''', unsafe_allow_html=True)
