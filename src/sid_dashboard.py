"""Sid's overview, using the same active records and P&L calculations as reports."""
import calendar
import datetime as dt
import html
import json
from collections import defaultdict
from zoneinfo import ZoneInfo
import streamlit as st
import streamlit.components.v1 as components
from .branch_names import canonical_branch
from .expense_linking import link_expenses_to_trips
from .expense_periods import allocate_expenses_for_period
from .number_format import format_inr
from .operational_dates_v2 import OPERATIONS_START


def data(value):
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value or '{}')
    except (ValueError, TypeError):
        return {}


def date_value(value, local=False):
    if isinstance(value, dt.datetime):
        if local:
            value = (value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)).astimezone(ZoneInfo('Asia/Kolkata'))
        return value.date()
    if isinstance(value, dt.date):
        return value
    if value:
        try:
            return date_value(dt.datetime.fromisoformat(str(value)), local)
        except ValueError:
            pass
    return None


def dashboard_summary(rows, start, end, pnl_builder):
    active = [r for r in rows if not r.get('is_archived') and r.get('status') != 'Cancelled']
    users, branches = defaultdict(lambda: [0, 0]), {b:[0, 0] for b in ('Andheri','Wada','Pune','Vadodara')}
    for row in active:
        saved = date_value(row.get('created_at'), local=True)
        if saved and start <= saved <= end:
            slot = 1 if row.get('report_scope') == 'Expense' else 0
            users[str(row.get('created_by') or 'Not specified')][slot] += 1
            branch = canonical_branch(row.get('branch')) or 'Not specified'
            branches.setdefault(branch, [0, 0])[slot] += 1
    month_start = end.replace(day=1)
    month_end = end.replace(day=calendar.monthrange(end.year, end.month)[1])
    month_rows = [r for r in active if date_value(r.get('trip_date')) and month_start <= date_value(r['trip_date']) <= month_end]
    all_trips = [r for r in active if r.get('report_scope') != 'Expense']
    trips = [r for r in month_rows if r.get('report_scope') != 'Expense']
    expenses = link_expenses_to_trips([r for r in active if r.get('report_scope') == 'Expense'], all_trips)
    expenses = allocate_expenses_for_period([{**r, 'categories': data(r.get('dtr_data')).get('categories', {})} for r in expenses], month_start, month_end)
    pnl = pnl_builder(trips, expenses)
    total = next((r for r in pnl if r.get('Branch') == 'Total'), {})
    revenue, expense, profit = (float(total.get(k) or 0) for k in ('Total Revenue', 'Expense', 'Profit'))
    return {'users': sorted(users.items(), key=lambda item:(-sum(item[1]), item[0])), 'branches': list(branches.items()),
            'total': sum(sum(counts) for counts in users.values()), 'revenue':revenue, 'expense':expense, 'profit':profit,
            'margin': profit / revenue * 100 if revenue else 0, 'month_entries':len(month_rows),
            'month_start':month_start, 'month_end':month_end}


def esc(value):
    return html.escape(str(value))


PATHS = {
    'chart':'<path d="M3 21V11h4v10M10 21V6h4v15M17 21V2h4v19"/>',
    'person':'<circle cx="12" cy="7" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3"/>',
    'users':'<circle cx="9" cy="7" r="4"/><path d="M2 21v-2a7 7 0 0 1 14 0v2M17 3a4 4 0 0 1 0 8m1 3a6 6 0 0 1 4 6"/>',
    'branch':'<circle cx="12" cy="4" r="3"/><circle cx="4" cy="20" r="3"/><circle cx="20" cy="20" r="3"/><path d="M12 7v5M4 17v-5h16v5"/>',
    'coins':'<ellipse cx="12" cy="4" rx="8" ry="3"/><path d="M4 4v15c0 4 16 4 16 0V4M4 9c0 4 16 4 16 0M4 14c0 4 16 4 16 0"/>',
    'layers':'<path d="m12 2 10 6-10 6L2 8zM2 13l10 6 10-6M2 18l10 6 10-6"/>',
    'calendar':'<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 2v6m10-6v6M3 11h18"/>',
    'target':'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="m12 12 8-8"/>',
}


def icon(name):
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</svg>'


def heading(title, name):
    return f'<div class="dash-heading"><span>{icon(name)}</span><h3>{esc(title)}</h3></div>'


def activity_table(items, first, total=False):
    markup = f'<div class="dash-table-scroll"><table class="dash-table"><thead><tr><th>{first}</th><th>Trip Entries</th><th>Direct Expenses</th><th>Total Entries</th></tr></thead><tbody>'
    for name, counts in items:
        name_html = f'<span class="dash-user-name">{icon("person")} {esc(name)}</span>' if first == 'User' else esc(name)
        markup += f'<tr><td>{name_html}</td><td>{counts[0]}</td><td>{counts[1]}</td><td><b>{sum(counts)}</b></td></tr>'
    if total:
        trip, expense = (sum(counts[i] for _,counts in items) for i in (0,1))
        markup += f'<tr class="dash-total"><td>Total</td><td>{trip}</td><td>{expense}</td><td>{trip+expense}</td></tr>'
    if not items:
        markup += '<tr><td colspan="4">No entries saved in this period.</td></tr>'
    return markup + '</tbody></table></div>'


STYLE = '''<style>
.st-key-sid_dashboard{color:#0c173f}@media(min-width:751px){.st-key-sid_dashboard{margin-top:-48px}}.dash-intro{display:flex;gap:18px;align-items:center;margin:10px 0 22px}.dash-intro>span,.dash-heading>span{display:grid;place-items:center;background:linear-gradient(120deg,#eff6ff,#e5eeff);color:#0065ff;box-shadow:0 3px 7px #0065ff12;border-radius:16px;width:62px;height:62px;flex-shrink:0}.dash-intro svg{width:35px;height:35px}.dash-intro h1{padding:0!important;margin:0!important;font-size:32px!important;line-height:1.4}.dash-intro p{margin:0;color:#4f6086;font-size:16px}
.st-key-dash_users,.st-key-dash_branches,.st-key-dash_pnl,.st-key-dash_duplicates{background:linear-gradient(120deg,#fff,#f5f8ff);border:1px solid #e1eaff;border-radius:24px;padding:20px;box-shadow:0 6px 17px #165af00c;margin-bottom:18px;min-height:320px}
.dash-heading{display:flex;gap:14px;align-items:center;margin-bottom:16px}.dash-heading>span{width:40px;height:40px;border-radius:12px;background:#f5f9ff}.dash-heading svg{width:30px;height:30px}.dash-heading h3{font-size:21px!important;padding:0!important;margin:0!important;color:#0b163f;line-height:1.3}.dash-badge{color:#121b52;background:#e6efff;padding:10px 15px;border-radius:30px;font-weight:650;white-space:nowrap;text-align:center;font-size:14px}
.dash-table{width:100%;border:0!important;border-collapse:collapse;font-size:16px;color:#111b3f}.dash-table th{border:0!important;background:linear-gradient(110deg,#f5f8ff,#eaf1fc);padding:10px 12px;font-weight:600;text-align:center;white-space:nowrap}.dash-table th:first-child,.dash-table td:first-child{text-align:left}.dash-table td{border:0!important;padding:9px 12px;border-bottom:1px solid #e9effb;text-align:center}.dash-table td:first-child{font-weight:650}.dash-user-name{display:flex;align-items:center;gap:14px}.dash-user-name svg{width:24px;height:24px;color:#0065ff;background:#eaf2ff;border-radius:50%;padding:3px}.dash-table td:last-child{background:#eaf2ff88;border-radius:16px;font-weight:700}.dash-total{background:#e4eeff;font-weight:750}.dash-table-scroll{max-height:275px;overflow:auto}
.dash-finance{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:3px 0 16px}.dash-stat{border:1px solid #e4ecfc;border-radius:18px;padding:16px;background:linear-gradient(120deg,#f6faff,#eaf2ff)}.dash-stat small{color:#52618a;font-size:15px}.dash-stat strong{display:block;color:#005cff;font-size:clamp(19px,1.6vw,28px);font-weight:750;margin-top:8px;overflow-wrap:anywhere}.dash-stat.expense{background:linear-gradient(120deg,#faf8ff,#f0edff)}.dash-stat.expense strong{color:#3e16a0}.dash-stat.profit{background:linear-gradient(120deg,#f3fff2,#edfaeb)}.dash-stat.profit strong{color:#12820e}.dash-stat.loss strong{color:#ca243c}
.dash-bottom{display:grid;grid-template-columns:1fr 1fr;gap:15px}.dash-mini{display:flex;align-items:center;gap:15px;border:1px solid #e7edfb;border-radius:17px;padding:14px;background:#fbfdff}.dash-mini svg{width:34px;height:34px;color:#0065ff}.dash-mini strong{display:block;font-size:25px;font-weight:750;color:#17224f}.dash-mini small{font-size:15px;color:#3d4c78}.dash-mini .positive{color:#12820e}.dash-mini .negative{color:#ca243e}.dash-duplicate-body{display:flex;align-items:center;gap:35px;padding:20px;border:1px solid #e6edfc;border-radius:20px;background:#ffffff88;min-height:175px}.dash-duplicate-number{background:linear-gradient(110deg,#f0f5ff,#dfeaff);border-radius:20px;padding:16px 25px;min-width:42%}.dash-duplicate-number strong{display:block;color:#005dff;font-size:48px;line-height:1.4}.dash-duplicate-number span{color:#465982;font-size:17px}.dash-duplicate-facts p{font-size:17px;color:#344372;display:flex;align-items:center;gap:12px;margin:14px 0}.dash-duplicate-facts svg{width:24px;height:24px;flex-shrink:0}
.st-key-dash_pnl button{border:0;background:transparent;color:#0064ff;white-space:nowrap}.st-key-dash_duplicates button{background:linear-gradient(110deg,#238aff,#0054ff);border:0;color:white;border-radius:26px;font-size:14px;white-space:nowrap;box-shadow:0 4px 8px #0064ff2b}
@media(max-width:750px){.dash-intro h1{font-size:26px!important}.st-key-dash_users,.st-key-dash_branches,.st-key-dash_pnl,.st-key-dash_duplicates{padding:14px;min-height:0}.dash-heading h3{font-size:18px!important}.dash-table{font-size:13px}.dash-table th,.dash-table td{border:0!important;padding:8px 5px}.dash-finance{gap:6px}.dash-stat{padding:10px 7px}.dash-stat small{font-size:11px}.dash-stat strong{font-size:15px}.dash-mini{padding:10px;gap:8px}.dash-mini strong{font-size:20px}.dash-mini small{font-size:12px}.dash-duplicate-body{gap:12px;padding:12px}.dash-duplicate-number{padding:12px}.dash-duplicate-number strong{font-size:36px}.dash-duplicate-number span,.dash-duplicate-facts p{font-size:13px}}
</style>'''


def switch_to_reports():
    components.html('''<script>let n=0;const t=setInterval(()=>{const tabs=Array.from(window.parent.document.querySelectorAll('[role="tab"]'));const tab=tabs.find(x=>x.innerText.trim()==='Generate Reports');if(tab){tab.click();clearInterval(t)}else if(++n>30)clearInterval(t)},100)</script>''', height=0)


@st.fragment
def render_dashboard(user, rows, groups, pnl_builder, review):
    if user != 'Sid':
        return
    st.markdown(STYLE, unsafe_allow_html=True)
    with st.container(key='sid_dashboard'):
        title, dates = st.columns([3, 1.2], vertical_alignment='center')
        title.markdown(f'<div class="dash-intro"><span>{icon("chart")}</span><div><h1>Dashboard</h1><p>Your weekly operations at a glance.</p></div></div>', unsafe_allow_html=True)
        today = dt.datetime.now(ZoneInfo('Asia/Kolkata')).date()
        period = dates.date_input('Dashboard date range', value=(max(OPERATIONS_START,today-dt.timedelta(days=6)),today), min_value=OPERATIONS_START, format='DD/MM/YYYY', label_visibility='collapsed', key='sid_dashboard_dates')
        if len(period) != 2:
            st.info('Select both the start and end date.')
            return
        summary = dashboard_summary(rows, *period, pnl_builder)
        left, right = st.columns(2, gap='medium')
        weekly = 'This Week' if period == (today-dt.timedelta(days=6),today) else 'Selected Period'
        with left:
            with st.container(key='dash_users'):
                head, total = st.columns([2.7,1.1], vertical_alignment='center')
                head.markdown(heading(f'User Activity ({weekly})','users'), unsafe_allow_html=True)
                total.markdown(f'<div class="dash-badge">Total Entries: {summary["total"]}</div>', unsafe_allow_html=True)
                st.markdown(activity_table(summary['users'],'User'), unsafe_allow_html=True)
        with right:
            with st.container(key='dash_branches'):
                st.markdown(heading(f'Branch-wise Entries ({weekly})','branch'), unsafe_allow_html=True)
                st.markdown(activity_table(summary['branches'],'Branch',total=True), unsafe_allow_html=True)
        left, right = st.columns(2, gap='medium')
        with left:
            with st.container(key='dash_pnl'):
                title, action = st.columns([3,1], vertical_alignment='center')
                title.markdown(heading(f'Monthly P&L ({period[1]:%b %Y})','coins'), unsafe_allow_html=True)
                if action.button('View P&L →', key='dash_view_pnl', use_container_width=True):
                    # Run the full page once to apply report controls before rendering them.
                    st.session_state['dashboard_pnl_request'] = (summary['month_start'],summary['month_end'])
                    st.rerun()
                profit_class = 'profit' if summary['profit'] >= 0 else 'loss'
                st.markdown(f'''<div class="dash-finance"><div class="dash-stat"><small>Total Revenue</small><strong>{format_inr(summary['revenue'])}</strong></div><div class="dash-stat expense"><small>Total Expenses</small><strong>{format_inr(summary['expense'])}</strong></div><div class="dash-stat {profit_class}"><small>{'Profit' if summary['profit'] >= 0 else 'Loss'}</small><strong>{format_inr(summary['profit'])}</strong></div></div><div class="dash-bottom"><div class="dash-mini">{icon('target')}<div><small>Profit Margin</small><strong class="{'positive' if summary['margin'] >= 0 else 'negative'}">{summary['margin']:.1f}%</strong></div></div><div class="dash-mini">{icon('calendar')}<div><small>Total Entries (Month)</small><strong>{summary['month_entries']:,}</strong></div></div></div>''', unsafe_allow_html=True)
        with right:
            with st.container(key='dash_duplicates'):
                title, action = st.columns([2.4,1.5], vertical_alignment='center')
                title.markdown(heading('Duplicate Entries','layers'), unsafe_allow_html=True)
                if action.button('Review Duplicates →', key='dashboard_review_duplicates', use_container_width=True):
                    review(groups)
                copies = [r for group in groups for r in group['duplicates']]
                oldest = min((date_value(r.get('trip_date')) for r in copies if date_value(r.get('trip_date'))), default=None)
                st.markdown(f'''<div class="dash-duplicate-body"><div class="dash-duplicate-number"><strong>{len(copies)}</strong><span>Potential Duplicates</span></div><div class="dash-duplicate-facts"><p>{icon('layers')} {len(groups)} Groups</p><p>{icon('coins')} {len(copies)} Duplicate Entries</p><p>{icon('calendar')} Oldest: {oldest.strftime('%d %b %Y') if oldest else '—'}</p></div></div>''', unsafe_allow_html=True)
        st.caption('Activity counts use active entries and the date they were saved (IST). Monthly P&L uses trip/expense dates and the same expense allocations as Generate Reports. Duplicate review covers all active records.')
