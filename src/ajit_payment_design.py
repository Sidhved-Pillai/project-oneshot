"""Spacing for Ajit's freight, payment, fuel, summary and save rows."""
import streamlit as st


def render_ajit_payment_styles():
    st.markdown('''<style>
    .st-key-ajit_freight_inputs{padding-bottom:5px}
    .st-key-ajit_fuel_details{padding:10px 12px;border:1px solid #dce8ff;border-radius:12px;background:#eef5ff80}
    .st-key-ajit_payment_totals{padding-top:7px;border-top:1px solid #e0e8f6;margin-top:3px}
    .st-key-ajit_payment_footer{padding-top:4px}
    @media(max-width:750px){
      .st-key-ajit_freight_inputs>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"],
      .st-key-ajit_payment_inputs>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"],
      .st-key-ajit_fuel_details>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"],
      .st-key-ajit_payment_totals>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:10px!important}
      .st-key-ajit_payment_footer>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{flex-direction:column!important}
      .st-key-ajit_freight_inputs [data-testid="stColumn"],.st-key-ajit_payment_inputs [data-testid="stColumn"],.st-key-ajit_fuel_details [data-testid="stColumn"],.st-key-ajit_payment_totals [data-testid="stColumn"],.st-key-ajit_payment_footer [data-testid="stColumn"]{width:100%!important;min-width:0!important;max-width:100%!important}
      .st-key-ajit_fuel_details{padding:9px}
    }
    </style>''', unsafe_allow_html=True)
