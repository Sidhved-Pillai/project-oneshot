"""Client-side duplicate selection; mutations remain authorized and atomic on server."""
import hashlib
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from .sid_dashboard import data, date_value, esc, heading
from .number_format import format_inr
from .branch_names import canonical_branch
from .audit_view import local_time
from .dialog_browser import explicit_close_script

_review = components.declare_component('sid_dashboard_duplicate_review', path=str(Path(__file__).with_name('dashboard_duplicates_component')))


def review_payload(groups):
    def record(row):
        raw = data(row.get('dtr_data'))
        expense = row.get('report_scope') == 'Expense'
        date = date_value(row.get('trip_date'))
        saved = local_time(row.get('created_at'))
        return {'number':row['request_number'], 'date':date.strftime('%d %b %Y') if date else '—',
                'vehicle':row.get('vehicle_number') or '—',
                'route':' → '.join(str(row.get(k) or '—') for k in ('from_location','to_location')),
                'amount':format_inr(row.get('amount') if expense else row.get('revenue')),
                'branch':row.get('branch') or '—', 'expense':expense, 'heading':row.get('expense_type') or '', 'beneficiary':row.get('beneficiary_name') or '—',
                'lr':raw.get('LR No.') or '—', 'invoice':row.get('invoice_number') or '—',
                'creator':row.get('created_by') or '—', 'created':saved.strftime('%d %b %Y, %I:%M %p') if saved else '—'}
    return [{'branch':canonical_branch(g['original'].get('branch')) or 'Not specified',
             'original':record(g['original']), 'duplicates':[record(r) for r in g['duplicates']],
             'reason':('Exact expense details, beneficiary and category' if g['original'].get('report_scope') == 'Expense'
                       else 'Unique LR number' if g['original'].get('created_by') == 'Manish'
                       else 'Date, vehicle and invoice' if g['original'].get('invoice_number') else 'Date, vehicle, route and amounts')}
            for g in groups]


@st.dialog('Review Duplicate Entries', width='large', dismissible=True, on_dismiss='ignore')
def review_duplicates(user, groups, store, find_duplicates):
    if user not in {'Sid', 'Vinod', 'Nikhil'}:
        st.error('Duplicate review is available only to Sid, Vinod and Nikhil.')
        return
    from .sid_dashboard import STYLE
    st.markdown(STYLE, unsafe_allow_html=True)
    st.markdown('''<style>[role="dialog"]:has(.dash-review-heading){width:min(1500px,96vw)!important;max-width:96vw!important;max-height:94dvh;overflow-y:auto;border-radius:24px;background:linear-gradient(120deg,#fff,#f4f8ff)}[role="dialog"]:has(.dash-review-heading) div[style*="padding: 1.5rem 1.5rem 0.75rem"]{display:none!important}.dash-review-heading h3{font-size:30px!important;margin:0!important}.dash-review-heading p{color:#52658a}.dash-review-close button{border-radius:50%}.dash-review-chips{display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-end}.dash-review-chips span{border:1px solid #d4e1fc;border-radius:12px;padding:10px;background:#f4f8ff;color:#19224d;font-size:13px;white-space:nowrap}</style>''',unsafe_allow_html=True)
    components.html(explicit_close_script(), height=0)
    copies = [r for g in groups for r in g['duplicates']]
    oldest = min((date_value(r.get('trip_date')) for r in copies if date_value(r.get('trip_date'))), default=None)
    left, right = st.columns([3,2],vertical_alignment='center')
    left.markdown(f'<div class="dash-review-heading">{heading("Review Duplicate Entries","layers")}<p>Review potential duplicate entries, compare with the original, and delete the duplicate(s).</p></div>',unsafe_allow_html=True)
    branches = len({canonical_branch(g['original'].get('branch')) or 'Not specified' for g in groups})
    right.markdown(f'<div class="dash-review-chips"><span>◇ {branches} Branches</span><span>▤ {len(copies)} Entries</span><span>▣ Oldest: {oldest.strftime("%d %b %Y") if oldest else "—"}</span></div>',unsafe_allow_html=True)
    versions = {r['request_number']:str(r.get('updated_at')) for g in groups for r in [g['original'],*g['duplicates']]}
    signature = hashlib.sha256(repr(sorted(versions.items())).encode()).hexdigest()
    if not groups:
        st.success('No duplicate records found.')
        return
    result = _review(groups=review_payload(groups), signature=signature, key='dashboard_duplicate_selector', default=None)
    if not result or result.get('nonce') == st.session_state.get('dashboard_duplicate_action'):
        return
    st.session_state.dashboard_duplicate_action = result.get('nonce')
    if result.get('action') == 'cancel':
        st.rerun()
    if result.get('action') == 'delete':
        selected = result.get('numbers') or []
        allowed = {r['request_number'] for group in groups for r in group['duplicates']}
        if not selected or any(number not in allowed for number in selected):
            st.error('Select valid duplicate copies. Originals cannot be deleted here.')
            return
        try:
            count = store.delete_duplicate_copies(selected, versions, user, find_duplicates)
        except ValueError as error:
            st.error(str(error))
            st.info('Close and reopen duplicate review to load current records.')
            return
        st.session_state['dashboard_duplicate_notice'] = f'Deleted {count} duplicate copies. Originals were retained; deleted records remain recoverable.'
        st.rerun()
