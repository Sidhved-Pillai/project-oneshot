"""Presentation-only styling for Sid's compact New Entry preview."""
import base64
import streamlit as st


PATHS = {
    'calendar': '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 2v6m10-6v6M3 11h18m-9 3v4m-2-2h4"/>',
    'truck': '<path d="M3 5h11v13H3zM14 10h4l3 4v4h-7M7 5V2H3v3"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="19" r="2"/>',
    'person': '<circle cx="12" cy="7" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3"/>',
    'coins': '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v13c0 4 16 4 16 0V5M4 10c0 4 16 4 16 0M4 15c0 4 16 4 16 0"/>',
    'upload': '<path d="M7 18H5a4 4 0 0 1-1-8 8 8 0 0 1 16-1 5 5 0 0 1 0 10h-3M12 22V10m-4 4 4-4 4 4"/>',
}


def section_heading(title, icon):
    svg = f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{PATHS[icon]}</svg>'
    return f'<div class="sid-section-title"><span>{svg}</span><strong>{title}</strong></div>'


def render_sid_header(logo):
    image = base64.b64encode(logo.read_bytes()).decode('ascii')
    st.markdown(f'''<div class="sid-topbar"><div class="sid-brand"><img src="data:image/png;base64,{image}" alt="OneShot"/><div><strong>Project <b>OneShot</b></strong><small>One record. Every operations report.</small></div></div></div>''', unsafe_allow_html=True)


def render_sid_styles():
    st.markdown('''<style>
    /* Only emitted for Sid. Keep native controls, callbacks and tab contents. */
    .app-hero{display:none!important}
    [data-testid="stElementContainer"]:has(>.stMarkdown .app-hero){display:none!important}
    .block-container{max-width:1670px!important;padding:112px 3.7% 25px!important}
    .block-container>[data-testid="stVerticalBlock"]{gap:0!important}
    [data-testid="stHeader"]{display:none!important}
    .stApp,[data-testid="stAppViewContainer"]{background:radial-gradient(ellipse at 80% 5%,#e0edffb3,transparent 40%),linear-gradient(125deg,#f5f8ff,#f8faff)!important}
    .sid-topbar{position:fixed;z-index:990;inset:0 0 auto;height:76px;background:#f9fbffed;border-bottom:1px solid #dbe7ff;border-radius:0 0 22px 22px;box-shadow:0 3px 8px #005bff0a;backdrop-filter:blur(15px)}
    .sid-brand{position:absolute;left:max(3.7%,calc((100vw - 1550px)/2));top:11px;display:flex;align-items:center;gap:12px;color:#081238}
    .sid-brand img{width:49px;height:49px;border-radius:13px;box-shadow:0 3px 8px #005bff12}
    .sid-brand strong{font-size:23px;letter-spacing:-1px;line-height:1.2}.sid-brand b{color:#0065ff}.sid-brand small{display:block;font-size:11px;font-weight:600;margin-top:3px}
    .st-key-sid_logout{position:fixed!important;z-index:1000;top:17px;right:3.7%;width:125px!important}
    .st-key-sid_logout button{height:40px!important;min-height:40px!important;font-size:13px!important;background:#fff!important;border:1px solid #e2eaff!important;box-shadow:0 3px 7px #0066ff14}
    .stTabs [data-baseweb="tab-list"]{position:fixed!important;z-index:999;top:15px;left:max(360px,calc((100vw - 1550px)/2 + 340px));right:calc(3.7% + 145px);width:auto!important;max-width:none!important;height:46px!important;justify-content:space-between;gap:4px!important;padding:0!important;margin:0!important;background:none!important;border:0!important;border-radius:0!important;box-shadow:none!important;backdrop-filter:none!important;overflow:visible!important}
    .stTabs [data-baseweb="tab-list"]:before{display:none!important}
    @media(min-width:751px){
      .stTabs [data-baseweb="tab-list"]{justify-content:flex-start!important;gap:12px!important}
      [data-testid="stTabs"] [data-testid="stTab"]{flex:0 0 auto!important}
    }
    [data-testid="stTabs"] [data-testid="stTab"]{height:42px!important;font-size:12px!important;padding:7px 11px!important;color:#091236!important;gap:7px!important}
    [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"]{background:linear-gradient(120deg,#258aff,#0054ff)!important;color:white!important;border-color:transparent!important;box-shadow:0 4px 9px #0068ff2a!important}
    [data-testid="stTabs"] [data-testid="stTab"]:after{display:none!important}
    [data-testid="stTabs"] [data-testid="stTab"]:before{font-family:'Material Symbols Rounded';font-size:22px;line-height:1;content:'calendar_add_on'}
    [data-testid="stTabs"] [data-testid="stTab"]:nth-child(2):before{content:'layers'}
    [data-testid="stTabs"] [data-testid="stTab"]:nth-child(3):before{content:'calendar_month'}
    [data-testid="stTabs"] [data-testid="stTab"]:nth-child(4):before{content:'work'}
    [data-testid="stTabs"] [data-testid="stTab"]:nth-child(5):before{content:'bar_chart'}
    [data-testid="stTabs"] [data-testid="stTab"]:nth-child(6):before{content:'history'}
    [data-baseweb="tab-border"]{display:none!important}
    .stTabs [data-baseweb="tab-panel"]{padding-top:0!important}
    .st-key-sid_entry_preview{color:#0a1238!important}
    .st-key-sid_entry_preview [data-testid="stVerticalBlock"]{gap:8px!important}
    .st-key-sid_entry_preview [data-testid="stHorizontalBlock"]{gap:12px!important}
    .sid-page-title{margin:0 0 13px 26px}.sid-page-title h1{font-size:36px!important;line-height:1.15!important;letter-spacing:-1px!important;font-weight:800!important;padding:0!important;margin:0 0 4px!important;color:#080f36!important}.sid-page-title p{font-size:16px!important;margin:0!important;color:#344468}
    .st-key-sid_basic_panel,.st-key-sid_vehicle_panel,.st-key-sid_beneficiary_panel,.st-key-sid_payment_panel,.st-key-sid_evidence_panel{border:1px solid #fff!important;border-radius:23px!important;background:linear-gradient(125deg,#ffffffd9,#f7f9ffe6)!important;box-shadow:0 4px 8px #005bff12!important;padding:10px 14px!important}
    .st-key-sid_basic_panel{min-height:350px!important;justify-content:space-between!important}
    .st-key-sid_vehicle_panel{min-height:180px!important;justify-content:space-between!important}
    .st-key-sid_beneficiary_panel{min-height:162px!important;justify-content:space-between!important}
    .st-key-sid_payment_panel{min-height:205px!important;justify-content:space-between!important}
    .sid-section-title{display:flex;align-items:center;gap:13px;height:34px;margin:-1px -3px 3px;border-radius:13px 13px 0 0;background:linear-gradient(90deg,#f4f7ff,#e8efff);color:#08113c}
    .sid-section-title>span{display:grid;place-items:center;width:43px;height:38px;background:linear-gradient(130deg,#fff,#eff5ff);border-radius:12px;color:#06f;box-shadow:0 2px 6px #005bff16}.sid-section-title svg{width:27px;height:27px}.sid-section-title strong{font-size:19px;letter-spacing:-.5px}
    .st-key-sid_entry_preview [data-testid="stWidgetLabel"]{min-height:0!important;margin-bottom:3px!important}
    .st-key-sid_entry_preview [data-testid="stWidgetLabel"] p{font-size:14px!important;line-height:18px!important;font-weight:600!important;color:#101318!important}
    .st-key-sid_entry_preview [data-baseweb="input"],.st-key-sid_entry_preview [data-baseweb="input"]>div,.st-key-sid_entry_preview [data-baseweb="select"]>div{height:34px!important;min-height:34px!important;border-radius:9px!important;background:#fff!important;border-color:#dce4f4!important;box-shadow:0 1px 2px #0044ff05!important}
    .st-key-sid_entry_preview [data-baseweb="select"]>div{padding-top:0!important;padding-bottom:0!important}
    .st-key-sid_entry_preview input,.st-key-sid_entry_preview [data-baseweb="select"]{font-size:14px!important;line-height:18px!important;color:#25385f!important}
    .st-key-sid_entry_preview input{height:32px!important;min-height:0!important;padding:4px 11px!important}
    .st-key-sid_entry_preview [data-testid="stDateInput"] input{font-weight:600!important}
    .st-key-sid_entry_preview [data-testid="stNumberInputContainer"]{height:34px!important;min-height:34px!important}
    .st-key-sid_entry_preview [data-testid="stTextArea"] textarea{font-size:13px!important;min-height:42px!important;height:42px!important;padding:8px 10px!important;resize:vertical}
    .st-key-sid_entry_preview [data-testid="stMetric"]{min-height:64px!important;padding:7px 11px!important;background:linear-gradient(120deg,#f4faff,#e3efff)!important;border:1px solid #e3edff!important;border-radius:14px!important}
    .st-key-sid_entry_preview [data-testid="stMetricLabel"] p{font-size:11px!important;color:#101a44!important}
    .st-key-sid_entry_preview [data-testid="stMetricValue"]{font-size:20px!important;line-height:27px!important;color:#0066ff!important;font-weight:800!important}
    .st-key-sid_entry_preview button[kind="primary"]{min-height:43px!important;height:43px!important;background:linear-gradient(120deg,#258aff,#0054ff)!important;color:white!important;border:0!important;border-radius:25px!important;box-shadow:0 4px 10px #0068ff25!important;font-size:14px!important}
    .st-key-sid_evidence_panel{padding:13px 20px!important;margin-bottom:6px!important;min-height:98px!important;justify-content:center!important}
    .st-key-sid_evidence_panel [data-testid="stHorizontalBlock"]{align-items:center!important}
    .sid-upload-title{display:flex;align-items:center;gap:24px;margin-left:80px}.sid-upload-title>span{display:grid;place-items:center;min-width:75px;height:61px;color:#06f;background:linear-gradient(135deg,#f5f9ff,#e3edff);border:1px solid #d5e2ff;border-radius:15px;box-shadow:0 3px 5px #003da327}.sid-upload-title svg{width:40px;height:40px}.sid-upload-title strong{font-size:19px;color:#0b133b}.sid-upload-title small{display:block;font-size:12px;color:#344468;margin-top:3px}
    .st-key-sid_evidence_panel [data-testid="stFileUploader"]{border:0!important;background:none!important;padding:0!important}
    .st-key-sid_evidence_panel [data-testid="stFileUploader"]>[data-testid="stWidgetLabel"],.st-key-sid_evidence_panel [data-testid="stFileUploaderDropzoneInstructions"]{display:none!important}
    .st-key-sid_evidence_panel [data-testid="stFileUploaderDropzone"]{border:0!important;background:none!important;padding:0!important;justify-content:center!important;box-shadow:none!important;transform:none!important}
    .st-key-sid_evidence_panel [data-testid="stFileUploaderDropzone"] button{min-width:210px;height:45px!important;border-radius:25px!important;border:0!important;background:linear-gradient(120deg,#258aff,#0054ff)!important;color:#fff!important;box-shadow:0 3px 8px #005bff25}
    .st-key-sid_evidence_panel [data-testid="stFileUploaderDropzone"] button:after{content:'⇧  Upload Files'!important;font-size:15px!important}
    .st-key-sid_evidence_panel [data-testid="stToggle"] label p{font-size:15px!important;font-weight:700!important;white-space:nowrap}
    .sid-upload-or{display:grid;place-items:center;width:33px;height:33px;border-radius:50%;border:1px solid #e1e8fb;background:white;font-size:12px;font-weight:700;box-shadow:0 3px 6px #003da31a}
    .st-key-sid_entry_preview [data-testid="stCaptionContainer"] p{font-size:11px!important;margin:0!important}
    @media(max-width:1200px){.stTabs [data-baseweb="tab-list"]{left:300px!important;right:165px!important}.sid-upload-title{margin-left:0;gap:12px}}
    @media(max-width:750px){.stTabs [data-baseweb="tab-list"]{top:68px!important;left:12px!important;right:12px!important;overflow-x:auto!important}.st-key-sid_basic_panel,.st-key-sid_vehicle_panel,.st-key-sid_beneficiary_panel,.st-key-sid_payment_panel{min-height:0!important}}
    @media(max-width:1200px){.sid-brand strong{font-size:19px}.sid-brand small{font-size:9px}.sid-brand img{width:40px;height:40px}.stTabs>[data-baseweb="tab-list"]{left:300px!important;right:165px!important}[data-testid="stTabs"] [data-testid="stTab"]{font-size:10px!important;padding:7px!important}[data-testid="stTabs"] [data-testid="stTab"]:before{display:none}.sid-upload-title strong{font-size:16px}.sid-upload-title>span{min-width:50px}.st-key-sid_evidence_panel [data-testid="stToggle"] label p{font-size:12px!important}}
    @media(max-width:750px){.block-container{padding:125px 12px 25px!important}.sid-topbar{height:112px}.stTabs>[data-baseweb="tab-list"]{top:68px!important;left:12px!important;right:12px!important;overflow-x:auto!important}.sid-brand{left:16px}.st-key-sid_logout{right:15px!important}.sid-page-title{margin-left:0}.sid-page-title h1{font-size:28px!important}.sid-upload-title small{font-size:10px}}
    @media(max-width:750px){
      .block-container{padding:calc(126px + env(safe-area-inset-top)) 12px 24px!important}
      .sid-topbar{height:calc(112px + env(safe-area-inset-top));border-radius:0 0 18px 18px}
      .sid-brand{top:calc(12px + env(safe-area-inset-top));left:12px;gap:8px}
      .sid-brand img{width:36px;height:36px}.sid-brand strong{font-size:17px;letter-spacing:-.6px}.sid-brand small{font-size:8px}
      .st-key-sid_logout{top:calc(12px + env(safe-area-inset-top))!important;right:12px!important;width:100px!important}
      .st-key-sid_logout button{height:36px!important;min-height:36px!important;padding:4px 10px!important;font-size:12px!important}
      .stTabs [data-baseweb="tab-list"]{top:calc(62px + env(safe-area-inset-top))!important;left:12px!important;right:12px!important;height:43px!important;justify-content:flex-start!important;gap:7px!important;overflow-x:auto!important;overflow-y:hidden!important;scrollbar-width:none;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch}
      .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar{display:none}
      [data-testid="stTabs"] [data-testid="stTab"]{flex:0 0 auto!important;width:max-content!important;min-width:max-content!important;height:36px!important;font-size:12px!important;padding:7px 12px!important;overflow:visible!important;white-space:nowrap!important}
      .sid-page-title{margin:0 0 12px}.sid-page-title h1{font-size:27px!important}.sid-page-title p{font-size:13px!important;line-height:1.45}
      .st-key-sid_entry_preview [data-testid="stHorizontalBlock"]{gap:10px!important}
      .st-key-sid_basic_panel,.st-key-sid_vehicle_panel,.st-key-sid_beneficiary_panel,.st-key-sid_payment_panel{padding:12px!important;border-radius:18px!important;min-height:0!important}
      .st-key-sid_entry_preview [data-testid="stWidgetLabel"] p{font-size:12px!important;line-height:17px!important}
      .st-key-sid_entry_preview input,.st-key-sid_entry_preview textarea,.st-key-sid_entry_preview [data-baseweb="select"]{font-size:16px!important}
      .st-key-sid_entry_preview [data-baseweb="input"],.st-key-sid_entry_preview [data-baseweb="input"]>div,.st-key-sid_entry_preview [data-baseweb="select"]>div,.st-key-sid_entry_preview [data-testid="stNumberInputContainer"]{height:42px!important;min-height:42px!important}
      .st-key-sid_entry_preview input{height:40px!important;padding:6px 9px!important}
      .sid-section-title{height:33px;margin-bottom:7px;gap:9px}.sid-section-title strong{font-size:17px}.sid-section-title>span{width:34px;height:34px}.sid-section-title svg{width:24px;height:24px}
      /* Pair fields inside cards, while the main left/right cards stack naturally. */
      .st-key-sid_basic_panel>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"],.st-key-sid_vehicle_panel>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"],.st-key-sid_beneficiary_panel>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;align-items:start!important}
      .st-key-sid_basic_panel>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"],.st-key-sid_vehicle_panel>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"],.st-key-sid_beneficiary_panel>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{width:100%!important;min-width:0!important;max-width:100%!important}
      .st-key-sid_vehicle_panel>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:nth-child(3){grid-column:1/-1}
      /* The dynamic payment row wraps into two usable columns, including fuel details. */
      .st-key-sid_payment_panel>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]:has(>[data-testid="stColumn"]:nth-child(7)){display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;align-items:start!important}
      .st-key-sid_payment_panel>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{min-width:0!important;max-width:100%!important;width:100%!important}
      .st-key-sid_payment_panel>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]:not(:has(>[data-testid="stColumn"]:nth-child(7))){flex-direction:column!important}
      .st-key-sid_payment_panel>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:6px!important}
      .st-key-sid_payment_panel>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{min-width:0!important;max-width:100%!important;width:100%!important}
      .st-key-sid_entry_preview [data-testid="stMetric"]{padding:7px!important;min-height:76px!important;border-radius:12px!important}
      .st-key-sid_entry_preview [data-testid="stMetricLabel"] p{font-size:10px!important;white-space:normal!important;line-height:13px!important}
      .st-key-sid_entry_preview [data-testid="stMetricValue"]{font-size:clamp(12px,3.35vw,16px)!important;line-height:24px!important;white-space:normal!important;overflow-wrap:anywhere}
      .st-key-sid_entry_preview [data-testid="stTextArea"] textarea{height:62px!important;min-height:62px!important}
      .st-key-sid_payment_panel button[kind="primary"]{width:100%!important;height:46px!important;min-height:46px!important}
      /* Two clear evidence actions below a single small heading. */
      .st-key-sid_evidence_panel{padding:12px!important;min-height:0!important;border-radius:18px!important}
      .st-key-sid_evidence_panel>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;align-items:center!important;gap:12px!important}
      .st-key-sid_evidence_panel>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{min-width:0!important;width:100%!important;max-width:100%!important}
      .st-key-sid_evidence_panel>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:first-child{grid-column:1/-1}
      .st-key-sid_evidence_panel>[data-testid="stLayoutWrapper"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:nth-child(3){display:none!important}
      .sid-upload-title{margin:0;gap:10px}.sid-upload-title>span{min-width:42px;width:42px;height:42px;border-radius:11px}.sid-upload-title svg{width:28px;height:28px}.sid-upload-title strong{font-size:16px}.sid-upload-title small{font-size:9px;line-height:13px;margin-top:2px}
      .st-key-sid_evidence_panel [data-testid="stFileUploaderDropzone"] button{width:100%!important;min-width:0!important;height:42px!important;padding:6px 10px!important}
      .st-key-sid_evidence_panel [data-testid="stFileUploaderDropzone"] button:after{font-size:13px!important}
      .st-key-sid_evidence_panel [data-testid="stToggle"] label p{font-size:12px!important;white-space:normal!important;line-height:16px!important}
    }
    </style>''', unsafe_allow_html=True)
