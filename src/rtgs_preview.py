"""Read-only confirmation of exactly the rows included in a bank workbook."""
import html
import streamlit as st
import streamlit.components.v1 as components
from .dialog_browser import explicit_close_script
from .number_format import format_inr

PREVIEW_COLUMNS = ['Sr. No.', 'Branch', 'Transporter Name', 'Vehicle No.', 'Invoice No.', 'Beneficiary', 'Amount']


def preview_table(frame):
    def esc(value):
        return html.escape(str(value if value is not None else ''))
    header = ''.join(f'<th>{"Amount (₹)" if c == "Amount" else esc(c)}</th>' for c in PREVIEW_COLUMNS)
    body = ''.join('<tr>' + ''.join(
        f'<td class="{"money" if c == "Amount" else ""}">{esc(format_inr(row.get(c, 0)) if c == "Amount" else row.get(c, ""))}</td>'
        for c in PREVIEW_COLUMNS) + '</tr>' for row in frame.to_dict('records'))
    return f'<div class="rtgs-preview-table" tabindex="0" aria-label="Selected RTGS records"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>'


@st.dialog('Create RTGS Report', width='large', dismissible=True, on_dismiss='ignore')
def preview_rtgs_report(frame, report_file, request_numbers, start, end, on_confirm):
    st.markdown('''<style>
    [role="dialog"]:has(.rtgs-preview-marker){width:min(1150px,96vw)!important;max-width:96vw!important;border-radius:24px;background:linear-gradient(120deg,#fff,#f5f8ff);color:#080f42;padding:8px;max-height:94dvh;overflow-y:auto}
    [role="dialog"]:has(.rtgs-preview-marker)>div:first-child{display:none!important}
    [role="dialog"]:has(.rtgs-preview-marker) button[aria-label="Close"]{display:none!important}
    .rtgs-preview-title{font-size:30px!important;line-height:1.2!important;color:#080f42!important;font-weight:800!important;margin:8px 0 10px!important;padding:0!important}
    .rtgs-preview-dismiss{width:100%;font:inherit;cursor:pointer;padding:10px 15px;box-sizing:border-box}
    .st-key-rtgs_preview_close button{border:0!important;background:transparent!important;color:#080f42!important;font-size:26px;min-height:35px;padding:0!important}
    .rtgs-preview-marker{color:#334575;margin:0 0 12px;font-size:14px}
    .rtgs-preview-panel{padding:12px;border:1px solid #d5e1ff;border-radius:16px;background:#fbfdff;box-shadow:0 2px 5px #234fff10}
    .rtgs-preview-table{max-height:365px;overflow:auto;border:1px solid #dce5fb;border-radius:12px;scrollbar-color:#2d73f5 #e5edfc;scrollbar-width:auto}
    .rtgs-preview-table table{width:100%;border-collapse:separate;border-spacing:0;white-space:nowrap;font-size:13px;color:#101740}
    .rtgs-preview-table th{position:sticky;top:0;background:#e7eafb;text-align:left;font-weight:750;z-index:1}
    .rtgs-preview-table td,.rtgs-preview-table th{padding:8px 10px;border-bottom:1px solid #e8edf9;border-right:1px solid #eef1f9}
    .rtgs-preview-table tr:nth-child(even){background:#f7f9ff}.rtgs-preview-table td.money{text-align:right;font-weight:750}
    .rtgs-preview-table::-webkit-scrollbar{width:15px;height:15px}.rtgs-preview-table::-webkit-scrollbar-track{background:#e5edfc;border-radius:8px}.rtgs-preview-table::-webkit-scrollbar-thumb{background:#2d73f5;border:3px solid #e5edfc;border-radius:8px}
    .st-key-rtgs_preview_confirm button{background:linear-gradient(110deg,#10b82a,#008b09)!important;color:white!important;border:0!important;border-radius:13px!important;min-height:44px;font-weight:700}
    .st-key-rtgs_preview_cancel button{background:white!important;color:#080f42!important;border:1px solid #ccd5e9!important;border-radius:13px!important;min-height:44px}
    </style>''', unsafe_allow_html=True)
    title, close = st.columns([12, 1], vertical_alignment='center')
    title.markdown('<h2 class="rtgs-preview-title">Create RTGS Report</h2>', unsafe_allow_html=True)
    with close, st.container(key='rtgs_preview_close'):
        st.markdown('<button type="button" class="rtgs-preview-dismiss" aria-label="Close preview">✕</button>', unsafe_allow_html=True)
    st.markdown(f'<p class="rtgs-preview-marker">Review {len(frame)} selected record(s) · Total: {html.escape(format_inr(frame["Amount"].sum()))}</p>', unsafe_allow_html=True)
    st.markdown('<div class="rtgs-preview-panel">'+preview_table(frame)+'</div>', unsafe_allow_html=True)
    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
    _, cancel, confirm = st.columns([5, 1.2, 1.4], vertical_alignment='center')
    with cancel, st.container(key='rtgs_preview_cancel'):
        st.markdown('<button type="button" class="rtgs-preview-dismiss">Cancel</button>', unsafe_allow_html=True)
    with confirm, st.container(key='rtgs_preview_confirm'):
        confirmed = st.download_button('Confirm', report_file, f'RTGS-{start}-{end}.xls', 'application/vnd.ms-excel',
                           type='primary', icon=':material/check:', use_container_width=True,
                           on_click=on_confirm, args=(list(request_numbers), start, end), key='confirm_rtgs_preview')
        if confirmed:
            st.rerun(scope='app')

    components.html(explicit_close_script() + preview_dismiss_script(), height=0, scrolling=False)


def preview_dismiss_script():
    """Use Streamlit's native local dismissal; never send Cancel to the server."""
    return '''<script>
(() => {
  const doc=window.parent.document;
  const bind=()=>{
    const dialog=doc.querySelector('[role="dialog"]:has(.rtgs-preview-marker)');
    if(!dialog)return false;
    const close=dialog.querySelector('button[aria-label="Close"]');
    if(!close)return false;
    for(const button of dialog.querySelectorAll('.rtgs-preview-dismiss')){
      button.onclick=event=>{event.preventDefault();event.stopPropagation();close.click()};
    }
    return true;
  };
  if(!bind()){
    const observer=new MutationObserver(()=>{if(bind())observer.disconnect()});
    observer.observe(doc.body,{childList:true,subtree:true});
    setTimeout(()=>observer.disconnect(),3000);
  }
})();
</script>'''
