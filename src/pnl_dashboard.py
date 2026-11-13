"""Daily P&L dashboard and drill-downs sharing the report accounting pipeline."""
import datetime as dt
import math
from collections import defaultdict
from zoneinfo import ZoneInfo

import streamlit as st

from .sid_dashboard import data, date_value, esc, icon, PATHS
from .branch_names import canonical_branch
from .expense_linking import link_expenses_to_trips
from .expense_periods import allocate_expenses_for_period
from .number_format import format_inr
from .operational_dates_v2 import OPERATIONS_START

DASHBOARD_USERS = {'Sid', 'Vinod', 'Nikhil'}
PATHS.update({
    'truck': '<path d="M2 5h12v13H2zM14 10h4l4 5v3h-8"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="19" r="2"/>',
    'trend': '<path d="m3 18 6-6 4 3 8-10M15 5h6v6"/>',
})
EXPENSE_LABELS = {'Extra Exp': 'Route / extra expenses', 'Passing Exp': 'Passing expense',
                  'Bill Discounting': 'Bill discounting', 'R & M': 'Repair & Maintenance',
                  'UPI': 'UPI / route expense'}


def period_model(rows, start, end, pnl_builder):
    active = [dict(r, dtr_data=data(r.get('dtr_data'))) for r in rows
              if not r.get('is_archived') and r.get('status') != 'Cancelled']
    all_trips = [r for r in active if r.get('report_scope') != 'Expense']
    trips = [r for r in all_trips if (day := date_value(r.get('trip_date'))) and start <= day <= end]
    expenses = link_expenses_to_trips([r for r in active if r.get('report_scope') == 'Expense'], all_trips)
    expenses = allocate_expenses_for_period(
        [{**r, 'categories': data(r.get('dtr_data')).get('categories', {})} for r in expenses], start, end)
    report = pnl_builder(trips, expenses)
    total = next((r for r in report if r.get('Branch') == 'Total'), {})
    revenue, expense, profit = (float(total.get(k) or 0) for k in ('Total Revenue', 'Expense', 'Profit'))
    revenue_rows, expense_rows = [], []
    for row in trips + expenses:
        is_expense = row.get('report_scope') == 'Expense'
        dtr = data(row.get('dtr_data'))
        common = {'Record': row.get('request_number', ''), 'Date': str(date_value(row.get('trip_date')) or ''),
                  'Branch': canonical_branch(row.get('branch')) or 'Not specified',
                  'Vehicle No.': row.get('vehicle_number') or '',
                  'Invoice No.': dtr.get('Invoice No.') or row.get('invoice_number') or '',
                  'From – To': ' → '.join(str(v or '') for v in (row.get('from_location'), row.get('to_location'))),
                  'Placed By': row.get('vehicle_placed_by') or dtr.get('Vehicle Placed By') or row.get('created_by') or '',
                  'Remarks': row.get('notes') or dtr.get('Remark') or ''}
        # Ask the same builder for each contributing source, never count advances twice.
        single = pnl_builder([] if is_expense else [row], [row] if is_expense else [])
        subtotal = next((r for r in single if r.get('Branch') == 'Total'), {})
        if not is_expense:
            revenue_rows.append({**common, 'Revenue': float(subtotal.get('Total Revenue') or 0)})
        for key, amount in subtotal.items():
            if key in {'Branch', 'Revenue-Own', 'Revenue OS', 'Total Revenue', 'Expense', 'Profit'}:
                continue
            if isinstance(amount, (int, float)) and amount:
                expense_rows.append({**common, 'Expense Type': EXPENSE_LABELS.get(key, key), 'Amount': float(amount),
                                     'Source': 'Direct Expense' if is_expense else 'Trip'})
    # Report rounds after grouping; reconcile fractional period allocations to its cents.
    for entries, field, target in ((revenue_rows, 'Revenue', revenue), (expense_rows, 'Amount', expense)):
        if entries:
            difference = round(target - math.fsum(r[field] for r in entries), 2)
            if difference:
                entries[-1][field] = round(entries[-1][field] + difference, 2)
    entry_rows = {}
    for row in revenue_rows + expense_rows:
        key = row['Record']
        entry = entry_rows.setdefault(key, {**row, 'Revenue': 0.0, 'Amount': 0.0})
        entry['Revenue'] += row.get('Revenue', 0.0)
        entry['Amount'] += row.get('Amount', 0.0)
    return {'entry_rows': list(entry_rows.values()), 'revenue': revenue, 'expense': expense, 'profit': profit,
            'margin': profit / revenue * 100 if revenue else 0,
            'revenue_rows': revenue_rows, 'expense_rows': expense_rows,
            'entry_count': len(trips) + len(expenses), 'direct_count': len(expenses),
            'report': report, 'start': start, 'end': end}


STYLE = '''<style>
.st-key-pnl_dashboard{color:#0b1647}.pnl-title{display:flex;align-items:center;gap:20px;margin:14px 0 22px}.pnl-title>span,.pnl-card-icon{display:grid;place-items:center;flex-shrink:0;width:74px;height:74px;border-radius:23px;background:linear-gradient(135deg,#f0f7ff,#dfeaff);color:#0064ff}.pnl-title svg{width:43px;height:43px}.pnl-title h1{font-size:36px!important;padding:0!important;margin:0!important}.pnl-title p{color:#4a5883;margin:0;font-size:17px}
[class*="st-key-plcard_"]{position:relative;border:1px solid #cdddff;border-radius:26px;padding:25px 22px;background:linear-gradient(125deg,#fbfdff,#dfeaff);min-height:165px;box-shadow:0 5px 14px #165af00a}.st-key-plcard_expense{background:linear-gradient(125deg,#fcfaff,#e9e1ff);border-color:#d8c8ff}.st-key-plcard_profit{background:linear-gradient(125deg,#fcfffc,#e5f9e4);border-color:#cceacc}.pl-card{min-width:0;display:flex;gap:24px;align-items:center;padding-right:35px}.pl-card svg{width:44px;height:44px}.pl-card small{font-size:20px;color:#101747;font-weight:650}.pl-card>div{min-width:0}.pl-card strong{display:block;font-size:clamp(28px,3vw,48px);line-height:1.5;color:#005aff;font-weight:800;overflow-wrap:anywhere}.st-key-plcard_expense strong{color:#4312a8}.st-key-plcard_expense .pnl-card-icon{color:#4312a8;background:#e9deff}.st-key-plcard_profit strong{color:#087b12}.st-key-plcard_profit .pnl-card-icon{color:#087b12;background:#e0fbdc}.pl-loss strong{color:#c12646!important}.pl-margin-badge{display:inline-block;background:#d6fbcf;color:#087b12;font-size:14px;font-weight:700;border-radius:18px;padding:3px 10px;margin-left:8px}
[class*="st-key-plcard_"] [data-testid="stButton"]{position:absolute;inset:0;z-index:2}[class*="st-key-plcard_"] button{width:100%!important;height:100%!important;background:transparent!important;border:0!important;color:transparent!important;box-shadow:none!important}[class*="st-key-plcard_"] button:focus-visible{outline:3px solid #0064ff!important}[class*="st-key-plcard_"]:hover{box-shadow:0 6px 22px #0064ff22}.pl-arrow{position:absolute;right:22px;top:calc(50% - 20px);border:1px solid #d8e4ff;border-radius:50%;background:#ffffffb8;width:40px;height:40px;display:grid;place-items:center;color:#0064ff;font-size:26px}
.st-key-pl_metrics{border:1px solid #e1eaff;border-radius:26px;background:#ffffffb8;padding:22px;margin:24px 0}.pl-mini{min-height:95px;padding:8px 12px;display:flex;gap:18px;align-items:center}.pl-mini svg{width:34px;height:34px;color:#0064ff}.pl-mini small{font-size:16px;font-weight:600}.pl-mini strong{display:block;font-size:30px;font-weight:750;line-height:1.6}[class*="st-key-plmini_"]{position:relative}[class*="st-key-plmini_"] [data-testid="stButton"]{position:absolute;inset:0;z-index:2}[class*="st-key-plmini_"] button{width:100%!important;height:100%!important;color:transparent!important;background:transparent!important}[class*="st-key-plmini_"]:hover{background:#edf4ff;border-radius:16px}.st-key-pl_metrics button{border:0;background:transparent;color:#0064ff;font-size:13px;padding:0 12px;min-height:24px}.st-key-pl_duplicates{border:1px solid #e1eaff;border-radius:26px;background:linear-gradient(125deg,#fff,#f3f7ff);padding:24px}.pl-dup{display:flex;align-items:center;gap:16px;min-height:95px}.pl-dup svg{width:46px;height:46px;color:#0064ff}.pl-dup h3{font-size:25px!important;padding:0!important;margin:0!important}.pl-dup p{color:#4e5c83;margin:0}.pl-dup-count{background:#e6eeff;border-radius:16px;padding:12px 22px}.pl-dup-count strong{font-size:36px;color:#005aff;display:block}.pl-chip{display:inline-block;padding:12px;border:1px solid #e1eaff;border-radius:13px;background:#fff;color:#18244d;margin:6px;font-weight:600}.st-key-pl_duplicates button{background:linear-gradient(110deg,#238aff,#0054ff);color:white;border:0;border-radius:28px;white-space:nowrap}
[role="dialog"]:has(.pl-dialog-title){width:min(1450px,95vw)!important;max-width:95vw!important;max-height:92dvh;overflow-y:auto;border-radius:25px;background:linear-gradient(120deg,#fff,#f5f8ff)}.pl-dialog-title{display:flex;gap:20px;align-items:center;margin-bottom:24px}.pl-dialog-title svg{width:42px;height:42px;color:#0064ff}.pl-dialog-title h2{font-size:30px!important;padding:0!important;margin:0!important}.pl-dialog-title p{margin:0;color:#52618a}.pl-dialog-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid #dbe5ff;border-radius:20px;margin-bottom:24px;overflow:hidden}.pl-dialog-stats>div{padding:20px;border-right:1px solid #e4ebff}.pl-dialog-stats strong{display:block;font-size:28px;color:#005aff;overflow-wrap:anywhere}.pl-summary{width:100%;border-collapse:collapse}.pl-summary td,.pl-summary th{padding:12px 18px;border:0;border-bottom:1px solid #e4eaff;text-align:left}.pl-summary td:last-child{text-align:right;font-weight:700}.pl-summary th{background:#e6edff}.pl-summary .expense{background:#efe8ff;color:#4312a8}.pl-summary .profit{background:#e7fbe3;color:#087b12}.pl-donut{width:240px;height:240px;margin:35px auto;border-radius:50%;display:grid;place-items:center}.pl-donut>div{background:#f9fbff;border-radius:50%;width:165px;height:165px;display:grid;place-content:center;text-align:center;color:#111b47;font-weight:700}.pl-entry-scroll{overflow-x:auto;border:1px solid #e0e8fc;border-radius:18px;margin:8px 0 16px}.pl-entries{width:100%;border-collapse:collapse;color:#111a40;font-size:15px}.pl-entries th{background:linear-gradient(110deg,#f2f6ff,#e9f0ff);text-align:left;padding:15px 17px;white-space:nowrap;border:0!important}.pl-entries td{padding:16px 17px;border:0!important;border-bottom:1px solid #e7edfa!important;white-space:nowrap}.pl-entries th:last-child,.pl-entries td:last-child{text-align:right}.pl-entries tbody tr:last-child td{border-bottom:0!important}.pl-branch{border-radius:20px;padding:5px 14px;font-weight:650;background:#e3efff;color:#005aff}.pl-branch.purple{background:#eee4ff;color:#4b15bd}.pl-branch.orange{background:#fff0e0;color:#964410}.pl-branch.green{background:#e3f7e7;color:#147d39}[role="dialog"]:has(.pl-dialog-title)>div[style*="padding: 1.5rem 1.5rem 0.75rem"]{display:none!important}[role="dialog"]:has(.pl-expense) .pl-dialog-stats strong{color:#4511a7}[role="dialog"]:has(.pl-direct) .pl-dialog-stats strong{color:#4511a7}.st-key-pl_metrics [data-testid="stColumn"]:not(:last-child){border-right:1px solid #dbe4fa}.st-key-pnl_dashboard [data-testid="stDateInput"] input{background:#fff!important;border:1px solid #dde7ff;border-radius:16px;padding:15px;font-size:17px}.pl-legend{text-align:center;font-size:17px;color:#33436a}
@media(max-width:750px){.pnl-title h1{font-size:27px!important}.pnl-title>span{width:54px;height:54px}.pnl-title p{font-size:14px}[class*="st-key-plcard_"]{padding:18px;min-height:130px}.pl-card small{font-size:17px}.pl-card{gap:14px;padding-right:30px}.pnl-card-icon{width:58px;height:58px}.pl-card strong{font-size:clamp(21px,6.6vw,30px)}.st-key-pl_metrics{padding:10px}.pl-mini{padding:8px;gap:10px}.pl-mini strong{font-size:23px}.pl-mini small{font-size:13px}.pl-dialog-stats{grid-template-columns:repeat(2,1fr)}.pl-dialog-stats>div{padding:12px}.pl-dialog-stats strong{font-size:20px}.st-key-pl_duplicates{padding:16px}}
</style>'''


def stats(items):
    st.markdown('<div class="pl-dialog-stats">' + ''.join(
        f'<div><span>{esc(label)}</span><strong>{esc(value)}</strong></div>' for label, value in items) + '</div>', unsafe_allow_html=True)


def entry_table(model, kind, key):
    entries = model['entry_rows'] if kind == 'entries' else model['revenue_rows'] if kind == 'revenue' else model['expense_rows']
    search, branch = st.columns([3, 1])
    query = search.text_input('Search entries', placeholder='Search invoice, vehicle, route or expense…', label_visibility='collapsed', key=key+'_search').strip().casefold()
    selected = branch.selectbox('Branch', ['All Branches'] + sorted({r['Branch'] for r in entries}), label_visibility='collapsed', key=key+'_branch')
    filtered = [r for r in entries if (selected == 'All Branches' or r['Branch'] == selected)
                and (not query or query in ' '.join(map(str, r.values())).casefold())]
    size = 6
    count = max(1, math.ceil(len(filtered)/size))
    page_key = key+'_page'
    fingerprint = (query, selected)
    if st.session_state.get(key+'_filter') != fingerprint:
        st.session_state[page_key] = 0
        st.session_state[key+'_filter'] = fingerprint
    page = min(st.session_state.get(page_key, 0), count-1)
    columns = (['Record', 'Invoice No.', 'Branch', 'Vehicle No.', 'From – To', 'Placed By', 'Revenue'] if kind == 'revenue'
               else ['Date', 'Branch', 'Expense Type', 'Vehicle No.', 'Amount', 'Remarks', 'Record', 'Source'])
    if kind == 'entries':
        columns = ['Record', 'Date', 'Branch', 'Vehicle No.', 'From – To', 'Revenue', 'Amount']
    money_field = 'Revenue' if kind == 'revenue' else 'Amount'
    def cell(row, column):
        value = row.get(column, '')
        if column in {'Revenue', 'Amount'}:
            return format_inr(value)
        if column == 'Branch':
            color = {'Wada':'blue','Pune':'purple','Vadodara':'orange','Andheri':'green'}.get(value,'blue')
            return f'<span class="pl-branch {color}">{esc(value)}</span>'
        return esc(value)
    st.markdown('<div class="pl-entry-scroll"><table class="pl-entries"><thead><tr>'
                + ''.join(f'<th>{esc(c)}</th>' for c in columns) + '</tr></thead><tbody>'
                + ''.join('<tr>'+''.join(f'<td>{cell(row,c)}</td>' for c in columns)+'</tr>'
                          for row in filtered[page*size:(page+1)*size])
                + ('<tr><td colspan="8">No entries match these filters.</td></tr>' if not filtered else '')
                + '</tbody></table></div>', unsafe_allow_html=True)
    footer, controls = st.columns([3, 2])
    footer.caption(f'Showing {page*size+1 if filtered else 0}–{min((page+1)*size,len(filtered))} of {len(filtered)} entries')
    with controls:
        prev, label, nxt = st.columns([1,2,1])
        if prev.button('‹', disabled=page == 0, key=key+'_prev'):
            st.session_state[page_key] = page-1
            st.rerun(scope='fragment')
        label.markdown(f'<div style="text-align:center;padding:8px;color:#005aff">{page+1} / {count}</div>', unsafe_allow_html=True)
        if nxt.button('›', disabled=page+1 == count, key=key+'_next'):
            st.session_state[page_key] = page+1
            st.rerun(scope='fragment')


@st.dialog('P&L details', width='large', dismissible=True, on_dismiss='ignore')
def show_details(model, kind, day_label):
    st.markdown(STYLE, unsafe_allow_html=True)
    titles = {'revenue': 'Revenue', 'expense': 'Expenses', 'profit': 'Profit & Loss', 'margin': 'Profit Margin',
              'entries': 'Total Entries', 'direct': 'Direct Expenses', 'month': 'P&L — Month to Date'}
    st.markdown(f'<div class="pl-dialog-title pl-{kind}">{icon("truck" if kind == "revenue" else "layers" if kind in {"expense","direct"} else "trend")}<div><h2>{titles[kind]}</h2><p>{esc(day_label)}</p></div></div>', unsafe_allow_html=True)
    from .dialog_browser import explicit_close_script
    import streamlit.components.v1 as components
    components.html(explicit_close_script(), height=0)
    expense_entries = len({r['Record'] for r in model['expense_rows']})
    if kind == 'revenue':
        stats([('Total Revenue',format_inr(model['revenue'])),('Total Entries',len(model['revenue_rows'])),
               ('Branches',len({r['Branch'] for r in model['revenue_rows']})),('Avg. Revenue / Entry',format_inr(model['revenue']/len(model['revenue_rows']) if model['revenue_rows'] else 0))])
        entry_table(model, 'revenue', 'pl_revenue')
    elif kind == 'entries':
        stats([('Total Entries', model['entry_count']), ('Trip Entries', len(model['revenue_rows'])),
               ('Direct Expenses', model['direct_count']), ('Profit / Loss', format_inr(model['profit']))])
        entry_table(model, 'entries', 'pl_all_entries')
    elif kind in {'expense','direct'}:
        display = model
        if kind == 'direct':
            display = {**model, 'expense_rows':[r for r in model['expense_rows'] if r['Source'] == 'Direct Expense']}
        amount = math.fsum(r['Amount'] for r in display['expense_rows'])
        stats([('Total Expenses',format_inr(amount)),('Expense Entries',len({r['Record'] for r in display['expense_rows']})),
               ('Branches',len({r['Branch'] for r in display['expense_rows']})),('% of Revenue',f'{amount/model["revenue"]*100:.1f}%' if model['revenue'] else '—')])
        entry_table(display, 'expense', 'pl_'+kind)
    else:
        stats([('Total Revenue',format_inr(model['revenue'])),('Total Expenses',format_inr(model['expense'])),
               ('Profit / Loss',format_inr(model['profit'])),('Profit Margin',f'{model["margin"]:.1f}%')])
        tab = st.radio('Detail view', ['P&L Summary',f'Revenue Entries ({len(model["revenue_rows"])})', f'Expense Entries ({expense_entries})'], horizontal=True, label_visibility='collapsed', key='pl_detail_view_'+kind)
        if tab.startswith('Revenue'):
            entry_table(model,'revenue','pl_summary_revenue')
        elif tab.startswith('Expense'):
            entry_table(model,'expense','pl_summary_expense')
        else:
            left, right = st.columns([1.2,1])
            totals = defaultdict(float)
            for row in model['expense_rows']:
                totals[row['Expense Type']] += row['Amount']
            left.markdown('<table class="pl-summary"><tr><th>Particulars</th><th>Amount (₹)</th></tr>'
                + f'<tr><td>Revenue (Total)</td><td>{format_inr(model["revenue"])}</td></tr><tr class="expense"><td colspan="2">Expenses</td></tr>'
                + ''.join(f'<tr><td>{esc(label)}</td><td>{format_inr(value)}</td></tr>' for label,value in totals.items())
                + f'<tr class="expense"><td>Total Expenses</td><td>{format_inr(model["expense"])}</td></tr><tr class="profit"><td>Profit / Loss</td><td>{format_inr(model["profit"])}</td></tr></table>', unsafe_allow_html=True)
            # A loss cannot be a negative pie slice: show expense coverage, with loss stated explicitly.
            ratio = max(0,min(100,model['margin']))
            right.markdown(f'<div class="pl-donut" style="background:conic-gradient(#97e993 0% {ratio}%,#d7baff {ratio}% 100%)"><div>{format_inr(model["revenue"])}<br>Total Revenue</div></div><p class="pl-legend">Profit / Loss: {format_inr(model["profit"])} ({model["margin"]:.1f}%)<br>Expenses: {format_inr(model["expense"])}</p>', unsafe_allow_html=True)


@st.fragment
def render_pnl_dashboard(user, rows, groups, pnl_builder, review):
    if user not in DASHBOARD_USERS:
        return
    st.markdown(STYLE, unsafe_allow_html=True)
    today = dt.datetime.now(ZoneInfo('Asia/Kolkata')).date()
    with st.container(key='pnl_dashboard'):
        title, date = st.columns([4,1], vertical_alignment='center')
        title.markdown(f'<div class="pnl-title"><span>{icon("coins")}</span><div><h1>P&L Dashboard</h1><p>Your daily operational summary from all entries.</p></div></div>', unsafe_allow_html=True)
        day = date.date_input('Dashboard date', value=max(today,OPERATIONS_START), min_value=OPERATIONS_START, format='DD/MM/YYYY', label_visibility='collapsed', key='pnl_dashboard_day')
        daily = period_model(rows,day,day,pnl_builder)
        month = period_model(rows,day.replace(day=1),day,pnl_builder)
        suffix = 'Today' if day == today else day.strftime('%d %b %Y')
        for col,kind,label,name in zip(st.columns(3),('revenue','expense','profit'),('Revenue','Expenses','Profit / Loss'),('truck','layers','trend')):
            with col.container(key='plcard_'+kind):
                st.markdown(f'<div class="pl-card {"pl-loss" if kind=="profit" and daily[kind]<0 else ""}"><span class="pnl-card-icon">{icon(name)}</span><div><small>{label} ({suffix})</small>{f'<span class="pl-margin-badge">{daily["margin"]:.1f}%</span>' if kind == 'profit' else ''}<strong>{format_inr(daily[kind])}</strong></div><span class="pl-arrow">→</span></div>', unsafe_allow_html=True)
                if st.button(f'View {label} entries',key='pl_open_'+kind,use_container_width=True):
                    show_details(daily,kind,day.strftime('%d %b %Y'))
        with st.container(key='pl_metrics'):
            items = [('margin','Profit Margin',f'{daily["margin"]:.1f}%','coins'),('entries','Total Entries',str(daily['entry_count']),'truck'),
                     ('direct','Direct Expenses',str(daily['direct_count']),'layers'),('month','P&L (Month to Date)',format_inr(month['profit']),'chart')]
            for col,(kind,label,value,name) in zip(st.columns(4),items):
                with col.container(key='plmini_'+kind):
                    st.markdown(f'<div class="pl-mini">{icon(name)}<div><small>{label}{" ("+suffix+")" if kind != "month" else ""}</small><strong>{esc(value)}</strong></div></div>',unsafe_allow_html=True)
                    if st.button('View '+label+' details',key='pl_open_'+kind):
                        show_details(month if kind=='month' else daily,kind,
                                     f'{day.replace(day=1):%d %b %Y} – {day:%d %b %Y}' if kind=='month' else day.strftime('%d %b %Y'))
        copies = [r for group in groups for r in group['duplicates']]
        oldest = min((date_value(r.get('trip_date')) for r in copies if date_value(r.get('trip_date'))),default=None)
        with st.container(key='pl_duplicates'):
            text, number, facts, action = st.columns([3,1.3,3,1.6],vertical_alignment='center')
            text.markdown(f'<div class="pl-dup">{icon("layers")}<div><h3>Duplicate Entries</h3><p>Review potential duplicate records and clean up your data.</p></div></div>',unsafe_allow_html=True)
            number.markdown(f'<div class="pl-dup-count"><strong>{len(copies)}</strong>Potential Duplicates</div>',unsafe_allow_html=True)
            facts.markdown(f'<span class="pl-chip">{len(groups)} Groups</span><span class="pl-chip">{len(copies)} Entries</span><span class="pl-chip">Oldest: {oldest.strftime("%d %b %Y") if oldest else "—"}</span>',unsafe_allow_html=True)
            if action.button('Review Duplicates →',key='dashboard_review_duplicates',use_container_width=True):
                review(groups)
        st.caption('P&L uses entry dates, saved trip costs and the same direct expense allocations as Generate Reports. Month to date ends on the selected day. Duplicate review covers all active records.')
