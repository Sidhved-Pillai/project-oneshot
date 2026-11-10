"""Logs dashboard: batched filters, paginated events, lazy read-only details."""
import datetime as dt
import html
import streamlit as st
from .audit_view import category, changes, event_data, flatten, local_time, module
from .number_format import format_inr


ICONS = {
    'history': '<path d="M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v6l4 2"/>',
    'person': '<circle cx="12" cy="7" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3"/>',
    'edit': '<path d="m16 3 5 5-13 13H3v-5zM13 6l5 5"/>',
    'trash': '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
    'chart': '<path d="M3 21V11h4v10M10 21V6h4v15M17 21V2h4v19"/>',
    'add': '<path d="M12 3v18M3 12h18"/>',
}


def icon(name):
    return f'<svg class="audit-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>'


def esc(value):
    return html.escape('—' if value is None or value == '' else str(value))


def display_value(field, value):
    monetary = {'Revenue', 'Amount', 'Transporter freight', 'Rtgs advance', 'Cash advance',
                'UPI', 'Diesel advance', 'Total advance', 'Balance amount', 'Payment / AMOUNT'}
    if value is not None and value != '' and (field in monetary or ' / categories / ' in field):
        try:
            float(value)
            return esc(format_inr(value))
        except (ValueError, TypeError):
            pass
    return esc(value)


def details_html(event):
    data = event_data(event)
    before, after = data.get('before'), data.get('after')
    label, color = category(event)
    snapshot = after or before or {}
    when = local_time(event.get('created_at'))
    summary = ' | '.join(f'{label}: {snapshot[k]}' for k, label in (('trip_date', 'Date'), ('vehicle_number', 'Vehicle'), ('branch', 'Branch')) if snapshot.get(k))
    content = f'<div class="audit-detail-title"><span>{icon("edit")}</span> Record Changes</div><p>{esc(event.get("action"))} by <b>{esc(event.get("user_name"))}</b> · {esc(when.strftime("%d %b %Y, %I:%M %p") if when else "")}</p><div class="audit-summary">{esc(event.get("request_number"))} · {esc(summary)}</div>'
    if before is not None and after is not None and label == 'Updated Record':
        diff = changes(before, after)
        content += f'<h3>Changes Made ({len(diff)} Fields)</h3><table class="audit-diff"><thead><tr><th>Field</th><th>Before (Previous Value)</th><th></th><th>After (Updated Value)</th></tr></thead><tbody>'
        for field, old, new in diff:
            content += f'<tr><td><b>{esc(field)}</b></td><td><span class="audit-old">{display_value(field, old)}</span></td><td class="audit-arrow">→</td><td><span class="audit-new">{display_value(field, new)}</span></td></tr>'
        content += '</tbody></table>'
        if not diff:
            content += '<p>No visible field values changed.</p>'
    elif data.get('report'):
        content += '<h3>Report details</h3><table class="audit-diff">'
        for field, value in data['report'].items():
            content += f'<tr><th>{esc(field)}</th><td>{esc(value)}</td></tr>'
        content += '</table><p>Recorded when the report download was requested.</p>'
    elif snapshot:
        content += '<h3>Last saved details</h3><table class="audit-diff">'
        for field, value in flatten(snapshot).items():
            if value is not None and value != '':
                content += f'<tr><th>{esc(field)}</th><td>{esc(value)}</td></tr>'
        content += '</table>'
    else:
        content += f'<div class="audit-summary">{esc(data.get("message"))}</div><p>Detailed before-and-after values were not captured for this historical activity.</p>'
    return content


STYLE = '''<style>
.st-key-audit_logs{color:#10183f}
.audit-icon{width:22px;height:22px;vertical-align:middle;flex-shrink:0}.audit-title .audit-icon{width:34px;height:34px}.audit-user{display:flex;align-items:center;gap:12px}.audit-user .audit-icon{color:#0064ff}
.audit-detail-title{display:flex;align-items:center;gap:20px}.audit-detail-title span{background:#e1edff;border-radius:16px;padding:14px;color:#0064ff}.audit-detail-title .audit-icon{width:32px;height:32px}
[role="dialog"]:has(.audit-detail-title){width:min(980px,94vw)!important;max-width:94vw!important;max-height:88dvh;overflow-y:auto;border-radius:22px;background:linear-gradient(120deg,#fff,#f4f8ff)}
.st-key-audit_filters [data-baseweb="select"]>div,.st-key-audit_filters [data-baseweb="input"]{background:#f8faff;border:1px solid #dce5f9;border-radius:12px}
[role="dialog"]:has(.audit-detail-title) div[style*="padding: 1.5rem 1.5rem 0.75rem"]{display:none}
.st-key-audit_pager{justify-content:flex-end!important}.st-key-audit_pager button[kind="primary"]{background:#0064ff!important;color:white!important}

.audit-title{display:flex;align-items:center;gap:18px;margin:12px 0 26px}.audit-title i{font-style:normal;color:#0764ff;background:#e7efff;border-radius:20px;padding:15px;font-size:34px}.audit-title h1{font-size:34px!important;margin:0!important;padding:0!important}.audit-title p{margin:3px 0;color:#536286}
.st-key-audit_filters,.st-key-audit_table{border:1px solid #e0e8fc;border-radius:23px;background:linear-gradient(120deg,#fff,#f5f8ff);padding:18px;box-shadow:0 5px 17px #174ec010}
.st-key-audit_table [data-testid="stHorizontalBlock"]{align-items:center;border-bottom:1px solid #e8edfa;padding:8px 0}
.audit-head{font-weight:700;background:#edf2fb;border-radius:12px;padding:10px 14px;color:#253050}
.audit-badge{display:inline-block;border-radius:22px;padding:7px 13px;font-weight:600;font-size:14px;white-space:nowrap}.audit-green{background:#e1f8e7;color:#157428}.audit-blue{background:#e1eeff;color:#005bef}.audit-red{background:#ffe5e7;color:#cf1d29}.audit-purple{background:#eee5ff;color:#6639ca}
.audit-message{font-weight:650;color:#101733}.audit-sub{font-size:13px;color:#52617b;overflow-wrap:anywhere}
.st-key-audit_table button{border-radius:22px;color:#0061ff;background:#e5efff;border:0;font-size:14px}.st-key-audit_pager button{border-radius:10px;min-width:35px}
.audit-detail-title{font-weight:750;font-size:30px;color:#10183f}.audit-summary{padding:18px;border:1px solid #cfe1ff;background:linear-gradient(110deg,#f7fbff,#e5f0ff);border-radius:17px;margin:18px 0;overflow-wrap:anywhere}
.audit-diff{width:100%;border-collapse:collapse;color:#131e42}.audit-diff th{text-align:left;background:#eaf0fb;padding:12px}.audit-diff td{padding:14px 10px;border-bottom:1px solid #e2e9fc;overflow-wrap:anywhere}.audit-old,.audit-new{display:inline-block;padding:8px 14px;border-radius:12px;white-space:pre-wrap}.audit-old{background:#ffe7eb;color:#5b2638}.audit-new{background:#e0f7e7;color:#145027}.audit-arrow{color:#2274ff;font-size:26px}
@media(max-width:750px){.st-key-audit_headers{display:none}.audit-title h1{font-size:27px!important}.st-key-audit_table{padding:10px}.audit-badge{font-size:12px;padding:5px 8px}.audit-diff td,.audit-diff th{padding:8px 4px;font-size:12px}}
</style>'''


@st.dialog('Activity details', width='large')
def show_changes(event, store):
    st.markdown(STYLE, unsafe_allow_html=True)
    enriched = store.activity_details(event) if hasattr(store, 'activity_details') else event
    st.markdown(details_html(enriched), unsafe_allow_html=True)


@st.fragment
def render_logs(rows, store):
    st.markdown(STYLE, unsafe_allow_html=True)
    newest = rows[0].get('id') if rows else None
    loaded = st.session_state.get('audit_loaded_rows')
    if loaded and loaded[0].get('id') == newest:
        rows = loaded
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date()
    title, dates = st.columns([3, 1.2], vertical_alignment='center')
    title.markdown(f'<div class="audit-title"><i>{icon("history")}</i><div><h1>Logs</h1><p>Track all activities, edits and changes in OneShot.</p></div></div>', unsafe_allow_html=True)
    period = dates.date_input('Activity dates', value=(today.replace(day=1), today), key='audit_dates', format='DD/MM/YYYY', label_visibility='collapsed')
    with st.container(key='audit_filters'):
        cols = st.columns([1, 1, 1, 2])
        activity = cols[0].selectbox('Activity', ['All Activities', 'Added Record', 'Updated Record', 'Deleted Record', 'Generated Report'], label_visibility='collapsed')
        user = cols[1].selectbox('User', ['All Users'] + sorted({r.get('user_name') or 'Unknown member' for r in rows}), label_visibility='collapsed')
        area = cols[2].selectbox('Module', ['All Modules', 'Records', 'Direct Expenses', 'Payments', 'Reports'], label_visibility='collapsed')
        search = cols[3].text_input('Search logs', placeholder='Search logs (e.g. Shyam, record no., vehicle, etc.)', label_visibility='collapsed')
    if len(period) != 2:
        st.info('Choose both a start and end date.')
        return
    filtered = [r for r in rows if (local_time(r.get('created_at')) is not None and period[0] <= local_time(r['created_at']).date() <= period[1])
                and (activity == 'All Activities' or category(r)[0] == activity)
                and (user == 'All Users' or r.get('user_name') == user)
                and (area == 'All Modules' or module(r) == area)
                and search.casefold() in ' '.join(str(r.get(k, '')) for k in ('user_name', 'action', 'request_number', 'details')).casefold()]
    signature = str((period, activity, user, area, search))
    if st.session_state.get('audit_signature') != signature:
        st.session_state.audit_signature = signature
        st.session_state.audit_page = 0
    pages = max(1, (len(filtered) + 7) // 8)
    page = min(st.session_state.get('audit_page', 0), pages - 1)
    with st.container(key='audit_table'):
        with st.container(key='audit_headers'):
            heads = st.columns([1.45, .85, 1.45, 3.2, 1.15])
            for head, title in zip(heads, ('Date & Time', 'User', 'Activity', 'Details', 'Changes')):
                head.markdown(f'<div class="audit-head">{title}</div>', unsafe_allow_html=True)
        for row in filtered[page * 8:(page + 1) * 8]:
            cols = st.columns([1.45, .85, 1.45, 3.2, 1.15], vertical_alignment='center')
            when = local_time(row['created_at'])
            cols[0].write(when.strftime('%d %b %Y, %I:%M %p'))
            cols[1].markdown(f'<div class="audit-user">{icon("person")}<b>{esc(row.get("user_name"))}</b></div>', unsafe_allow_html=True)
            label, color = category(row)
            cols[2].markdown(f'<span class="audit-badge audit-{color}">{icon({'green': 'add', 'blue': 'edit', 'red': 'trash', 'purple': 'chart'}[color])}　{esc(label)}</span>', unsafe_allow_html=True)
            data = event_data(row)
            snapshot = data.get('after') or data.get('before') or {}
            subtitle = ' | '.join(f'{label}: {snapshot[k]}' for k, label in (('lr_number', 'LR'), ('vehicle_number', 'Vehicle'), ('branch', 'Branch')) if snapshot.get(k))
            cols[3].markdown(f'<div class="audit-message">{esc(row.get("action"))}</div><div class="audit-sub">{esc(row.get("request_number"))} · {esc(subtitle or data.get("message", ""))}</div>', unsafe_allow_html=True)
            if cols[4].button('View Changes →', key=f'audit_view_{row["id"]}', use_container_width=True):
                show_changes(row, store)
        if not filtered:
            st.info('No activities match these filters.')
        st.caption(f'Showing {page * 8 + 1 if filtered else 0}–{min((page + 1) * 8, len(filtered))} of {len(filtered)} logs')
        with st.container(key='audit_pager', horizontal=True):
            choices = sorted({0, pages - 1, *range(max(0, page - 2), min(pages, page + 3))})
            if st.button('‹', disabled=page == 0, key='audit_prev'):
                st.session_state.audit_page = page - 1
                st.rerun(scope='fragment')
            previous = -1
            for index in choices:
                if previous >= 0 and index > previous + 1:
                    st.write('…')
                if st.button(str(index + 1), key=f'audit_page_{index}', type='primary' if index == page else 'secondary'):
                    st.session_state.audit_page = index
                    st.rerun(scope='fragment')
                previous = index
            if st.button('›', disabled=page >= pages - 1, key='audit_next'):
                st.session_state.audit_page = page + 1
                st.rerun(scope='fragment')
    if len(rows) >= 500 and hasattr(store, 'list_activity_logs'):
        if st.button('Load older activities', key='audit_older'):
            st.session_state.audit_loaded_rows = store.list_activity_logs(limit=len(rows) + 500)
            st.rerun(scope='fragment')
    st.caption('Times shown in IST. Historical events show only the evidence captured at the time. Load older activities to search further back.')
