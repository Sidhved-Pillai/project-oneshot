import datetime as dt
import math
from streamlit.testing.v1 import AppTest
from src.pnl_dashboard import period_model
from src.pnl_report import branch_pnl_summary

DAY = dt.date(2026,11,13)


def records():
    return [dict(request_number='T1', report_scope='Both', trip_date=DAY, branch='Wada',
                 ownership_type='Outside', revenue=20000, transporter_freight=12000, dtr_data={}),
            dict(request_number='T2', report_scope='Both', trip_date=DAY, branch='Pune',
                 ownership_type='Own', revenue=10000, diesel_advance=2000, upi=500,
                 dtr_data={'Toll Expense':100}),
            dict(request_number='E1', report_scope='Expense', trip_date=DAY, branch='Andheri',
                 dtr_data={'categories':{'Salary':1000,'Interest':100}}),
            dict(request_number='E2', report_scope='Expense', trip_date=DAY-dt.timedelta(days=20), branch='Wada',
                 dtr_data={'categories':{'Insurance':300},'periods':{'Insurance':{'start':'2026-11-01','end':'2026-11-30'}}})]


def test_daily_and_mtd_reconcile_to_report_and_drilldown():
    model = period_model(records(),DAY,DAY,branch_pnl_summary)
    assert model['revenue'] == 30000
    assert model['expense'] == 15710
    assert model['profit'] == 14290
    assert model['entry_count'] == 4 and model['direct_count'] == 2
    assert math.fsum(r['Amount'] for r in model['expense_rows']) == model['expense']
    assert sum(r['Revenue'] for r in model['revenue_rows']) == model['revenue']
    assert {r['Source'] for r in model['expense_rows']} == {'Trip','Direct Expense'}
    month=period_model(records(),DAY.replace(day=1),DAY,branch_pnl_summary)
    assert month['expense'] == 15830


def test_archived_cancelled_and_other_dates_excluded():
    rows=records()
    rows += [{**rows[0],'is_archived':True},{**rows[0],'status':'Cancelled'},
             {**rows[0],'trip_date':DAY+dt.timedelta(days=1)}]
    assert period_model(rows,DAY,DAY,branch_pnl_summary)['revenue'] == 30000


def test_zero_and_loss_are_finite():
    assert period_model([],DAY,DAY,branch_pnl_summary)['margin'] == 0
    m=period_model([records()[2]],DAY,DAY,branch_pnl_summary)
    assert m['profit'] == -1100 and m['revenue'] == 0


def app(user="Vinod"):
    from src.pnl_dashboard import render_pnl_dashboard
    from src.pnl_report import branch_pnl_summary
    render_pnl_dashboard(user,[],[],branch_pnl_summary,lambda groups:None)


def test_all_widgets_and_popups_render_without_database():
    ui=AppTest.from_function(app).run()
    assert not ui.exception
    assert len(ui.date_input)==1
    for key in ['pl_open_revenue','pl_open_expense','pl_open_profit','pl_open_margin','pl_open_entries','pl_open_direct','pl_open_month']:
        ui.button(key=key).click().run()
        assert not ui.exception
        assert any('class="pl-dialog-title' in m.value for m in ui.markdown)


def test_unknown_ownership_matches_report_instead_of_inventing_revenue():
    row={**records()[0],'ownership_type':''}
    model=period_model([row],DAY,DAY,branch_pnl_summary)
    assert model['revenue']==sum(r['Revenue'] for r in model['revenue_rows'])==0


def test_dashboard_duplicate_access_is_sid_only(tmp_path):
    import pytest
    from src.request_store import RequestStore
    from tests.test_sid_dashboard import seed, finder
    store=RequestStore(f'sqlite:///{tmp_path / "access.db"}')
    for user in ('Vinod','Nikhil'):
        ids=seed(store)
        versions={i:str(store.get(i)['updated_at']) for i in ids}
        with pytest.raises(ValueError, match='Only Sid'):
            store.delete_duplicate_copies([ids[-1]],versions,user,finder())
        assert not store.get(ids[-1])['is_archived']


def test_duplicates_section_only_rendered_for_sid():
    for user in ('Sid', 'Vinod', 'Nikhil'):
        ui = AppTest.from_function(app, args=(user,)).run()
        assert not ui.exception
        assert any(b.key == 'dashboard_review_duplicates' for b in ui.button) == (user == 'Sid')
        assert len([b for b in ui.button if b.key.startswith('pl_open_')]) == 7
