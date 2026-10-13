import datetime as dt

from sqlalchemy import event

from src.records_store_v14 import RequestStore


def test_consolidated_snapshot_matches_existing_reads_and_is_fresh(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'snapshot.db'}")
    number = store.create({'created_by':'Nitish', 'branch':'Pune', 'vehicle_number':'MH1234',
        'trip_date':dt.date(2026,10,1), 'report_scope':'Both', 'upi':100, 'balance_amount':200})
    store.create({'vehicle_number':'archived', 'trip_date':dt.date(2026,10,1), 'is_archived':True})
    store.send_balance_payment(number, 'Nitish')
    store.send_upi_payment(number, 'Nitish')
    expected = (store.list(status='All active'), store.list_balance_payments(),
                store.list_upi_payments(), store.list_activity_logs())
    queries, connections = [], []
    event.listen(store.engine, 'before_cursor_execute', lambda *args: queries.append(args[2]))
    event.listen(store.engine.pool, 'checkout', lambda *args: connections.append(1))
    assert store.dashboard_snapshot(include_logs=True) == expected
    assert len(queries) == 3 and len(connections) == 1
    store.update(number, {'revenue':1234})
    rows, balances, upi, logs = store.dashboard_snapshot(include_logs=True)
    assert rows[0]['revenue'] == 1234
    assert balances[number]['amount'] == 200 and upi[number]['amount'] == 100
    assert 'source_image' not in rows[0]


def test_users_without_payment_controls_skip_payment_queries(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'snapshot.db'}")
    queries = []
    event.listen(store.engine, 'before_cursor_execute', lambda *args: queries.append(args[2]))
    assert store.dashboard_snapshot(include_payments=False) == ([], {}, {}, [])
    assert len(queries) == 1
