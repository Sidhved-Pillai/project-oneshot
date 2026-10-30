import datetime as dt
import json
from zoneinfo import ZoneInfo

import pytest

from src.records_store_v18 import RequestStore
from src.invoice_viewer import invoice_viewer_html


def test_receipt_batch_commits_together_and_rolls_back_on_invalid_trip(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'batch.db'}")
    first = store.create({'created_by':'Ashok', 'vehicle_number':'TEST1', 'trip_date':dt.date(2026,10,26), 'dtr_data':{'LR Status':'Pending'}})
    second = store.create({'created_by':'Vijay', 'vehicle_number':'TEST2', 'trip_date':dt.date(2026,10,26), 'dtr_data':{'LR Status':'Pending'}})
    with pytest.raises(ValueError):
        store.mark_invoice_receipts({first:True, 'ZZZ-missing':True}, 'Shyam')
    assert json.loads(store.get(first)['dtr_data'])['LR Status'] == 'Pending'
    with pytest.raises(ValueError, match='Only Shyam'):
        store.mark_invoice_receipts({first:True}, 'Ajit')
    assert store.mark_invoice_receipts({first:True, second:True}, 'Shyam') == 2
    assert json.loads(store.get(first)['dtr_data'])['LR Status'] == 'Received'
    assert json.loads(store.get(second)['dtr_data'])['LR Status'] == 'Received'
    assert store.mark_invoice_receipts({first:False, second:True}, 'Shyam') == 1
    assert json.loads(store.get(first)['dtr_data'])['LR Status'] == 'Pending'


def test_receipt_preserves_trip_and_bank_data_and_first_received_date(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'receipt.db'}")
    number = store.create({'created_by':'Ashok','branch':'Vadodara','trip_date':dt.date(2026,9,1),'vehicle_number':'MH1234',
        'invoice_number':'INV1','revenue':1234,'rtgs_advance':100,'source_image':b'evidence',
        'dtr_data':{'LR No.':'LR1','LR Status':'Pending','custom':'keep'},
        'rtgs_data':{'BNF_NAME':'Transporter','BENE_ACC_NO':'001234'}})
    before = store.get(number)
    for user in ('Sid','Ajit','Ashok','Nitish'):
        with pytest.raises(ValueError, match='Only Shyam'):
            store.mark_invoice_received(number, user)
    assert store.mark_invoice_received(number, 'Shyam')
    after = store.get(number)
    raw = json.loads(after['dtr_data'])
    assert raw['LR Status'] == 'Received'
    assert raw['Received Date'] == dt.datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat()
    assert raw['custom'] == 'keep' and raw['LR No.'] == 'LR1'
    assert not store.mark_invoice_received(number, 'Shyam')
    assert store.get(number) == after
    for key in before:
        if key not in {'updated_at','dtr_data'}:
            assert before[key] == after[key]
    assert store.get_evidence(number)['source_image'] == b'evidence'
    from io import BytesIO
    import pandas as pd
    from src.trip_dtr_report import export_operational_dtr
    exported = pd.read_excel(BytesIO(export_operational_dtr(pd.DataFrame([raw]))))
    assert exported.iloc[0]['LR Status'] == 'Received'
    assert exported.iloc[0]['Received Date'].date().isoformat() == raw['Received Date']


@pytest.mark.parametrize('extra', [{'report_scope':'Expense'}, {'is_archived':True}, {'status':'Cancelled'}])
def test_receipt_rejects_nonactive_trips(tmp_path, extra):
    store = RequestStore(f"sqlite:///{tmp_path / 'receipt.db'}")
    number = store.create({'trip_date':dt.date(2026,10,1), 'vehicle_number':'MH1234', **extra})
    with pytest.raises(ValueError, match='active trip'):
        store.mark_invoice_received(number, 'Shyam')


def test_invoice_viewer_is_local_and_has_zoom_pan_rotate_controls():
    html = invoice_viewer_html(b'image', 'image/png')
    assert 'data:image/png;base64,aW1hZ2U=' in html
    assert 'Zoom in' in html and 'Zoom out' in html and 'Rotate clockwise' in html
    assert 'requestFullscreen' in html and 'onpointermove' in html
    assert 'https://' not in html


def test_record_action_order_and_shyam_only_tick():
    from pathlib import Path
    source = Path('app.py').read_text()
    start = source.index("action_names = ['edit']")
    end = source.index('record_widths =', start)
    actions = source[start:end]
    assert "append('balance')" not in actions and "append('upi')" not in actions
    assert actions.index("append('received')") < actions.index("append('delete')")
    assert "if current_user == 'Shyam':\n                action_names.append('received')" in actions
    assert "if current_user == 'Shyam' and not is_expense_record:" in source


@pytest.mark.parametrize('original', [{}, {'LR Status':'Pending', 'Received Date':''},
    {'LR Status':'In transit','Received Date':'2026-09-30'}])
def test_receipt_can_be_reversed_and_recorded_again(tmp_path, original):
    store = RequestStore(f"sqlite:///{tmp_path / 'toggle.db'}")
    number = store.create({'trip_date':dt.date(2026,10,1),'vehicle_number':'MH1234',
        'dtr_data':{**original,'other':'keep'}, 'revenue':1234})
    assert store.mark_invoice_received(number,'Shyam')
    with pytest.raises(ValueError, match='Only Shyam'):
        store.mark_invoice_received(number,'Sid',received=False)
    assert store.mark_invoice_received(number,'Shyam',received=False)
    row = store.get(number)
    assert json.loads(row['dtr_data']) == {**original,'other':'keep'}
    assert row['revenue'] == 1234
    assert not store.mark_invoice_received(number,'Shyam',received=False)
    assert store.get(number) == row
    assert store.mark_invoice_received(number,'Shyam')
    assert json.loads(store.get(number)['dtr_data'])['LR Status'] == 'Received'


def test_legacy_receipt_undo_uses_audit_snapshot(tmp_path):
    store = RequestStore(f"sqlite:///{tmp_path / 'legacy.db'}")
    number = store.create({'trip_date':dt.date(2026,10,1),'vehicle_number':'MH1234',
        'dtr_data':{'LR Status':'Pending','Received Date':'','other':'keep'}})
    assert store.mark_invoice_received(number,'Shyam')
    raw = json.loads(store.get(number)['dtr_data'])
    raw.pop('_hard_copy_previous')
    raw['other'] = 'later edit'
    store.update(number,{'dtr_data':raw})
    assert store.mark_invoice_received(number,'Shyam',received=False)
    assert json.loads(store.get(number)['dtr_data']) == {'LR Status':'Pending','Received Date':'','other':'later edit'}
