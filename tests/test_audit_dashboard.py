import datetime as dt
import json
import pytest
from sqlalchemy import select
from streamlit.testing.v1 import AppTest
from src.request_store import RequestStore, activity_logs
from src.audit_view import changes, event_data, local_time
from src.audit_ui import details_html


def test_atomic_audit_preserves_actual_before_and_actor(tmp_path):
    store = RequestStore(f'sqlite:///{tmp_path / "audit.db"}')
    number = store.create({'report_scope':'Expense','trip_date':dt.date(2026,10,11),
        'vehicle_number':'','created_by':'Nikhat','branch':'Vadodara','amount':2000,
        'dtr_data':{'categories':{"Driver's salary":2000}}})
    store.update(number, {'dtr_data':{'categories':{'Salary':2000,"Driver's salary":0}}}, 'records_tab', 'Shyam')
    logs = store.list_activity_logs()
    event = logs[0]
    data = event_data(store.activity_details(event))
    assert event['user_name'] == 'Shyam' and event['request_number'] == number
    assert data['before']['created_by'] == data['after']['created_by'] == 'Nikhat'
    assert ('DTR / categories / Salary', None, 2000) in changes(data['before'], data['after'])
    assert 'updated_at' not in str(changes(data['before'], data['after']))
    store.update(number, {'notes':'Later value'}, 'records_tab','Sid')
    assert 'Later value' not in details_html(store.activity_details(event))  # Historical event remains immutable.
    before = len(store.list_activity_logs())
    with pytest.raises(ValueError):
        store.update(number, {'notes':'stale'}, 'records_tab','Sid', expected_version='wrong')
    assert len(store.list_activity_logs()) == before


def test_deleted_snapshot_and_html_escaping(tmp_path):
    store = RequestStore(f'sqlite:///{tmp_path / "delete.db"}')
    number = store.create({'report_scope':'DTR','trip_date':dt.date(2026,11,10),'vehicle_number':'','created_by':'Ajit','notes':'<script>alert(1)</script>'})
    store.update(number, {'status':'Cancelled','is_archived':True},'records_soft_delete','Sid')
    event = store.list_activity_logs()[0]
    assert event['action'] == 'Deleted record'
    assert event_data(store.activity_details(event))['before']['is_archived'] is False
    markup = details_html(store.activity_details(event))
    assert '<script>' not in markup and '&lt;script&gt;' in markup
    assert local_time(dt.datetime(2026,11,10,12)).hour == 17


def test_unknown_history_does_not_invent_changes():
    markup = details_html({'action':'Updated record','details':'Old edit','user_name':'Shyam'})
    assert 'not captured' in markup
    assert 'Before (Previous Value)' not in markup


def audit_app():
    import datetime as dt
    from src.audit_ui import render_logs
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    render_logs([{'id':i,'created_at':now,'user_name':'Sid','action':'Updated record',
                  'request_number':f'REQ-{i}','details':'test'} for i in range(12)], object())


def test_dashboard_filters_pagination_and_popup():
    app = AppTest.from_function(audit_app).run()
    assert not app.exception
    assert len([b for b in app.button if b.label == 'View Changes →']) == 8
    next(b for b in app.button if b.label == 'View Changes →').click().run()
    assert not app.exception


def test_rtgs_status_audit_identifies_actor_and_exact_record(tmp_path):
    store = RequestStore(f'sqlite:///{tmp_path / "status.db"}')
    number = store.create({'vehicle_number':'TEST','report_scope':'DTR','trip_date':dt.date(2026,11,10),'created_by':'Ajit'})
    store.mark_rtgs_done([number], edited_by='Nikhat')
    event = store.list_activity_logs()[0]
    assert event['user_name'] == 'Nikhat' and event['request_number'] == number
    assert event_data(event)['before']['rtgs_done'] is False
    assert event_data(event)['after']['rtgs_done'] is True


def test_batch_changes_and_audit_roll_back_together(tmp_path):
    store = RequestStore(f'sqlite:///{tmp_path / "rollback.db"}')
    number = store.create({'vehicle_number':'TEST','report_scope':'DTR','trip_date':dt.date(2026,11,10),'created_by':'Ajit'})
    version = store.get(number)['updated_at']
    count = len(store.list_activity_logs())
    with pytest.raises(ValueError):
        store.update_many([(number,{'notes':'Never committed'}), ('missing',{'notes':'Fail'})],
                          'dtr_report_editor','Ashok', expected_versions={number:version})
    assert not store.get(number)['notes']
    assert len(store.list_activity_logs()) == count
