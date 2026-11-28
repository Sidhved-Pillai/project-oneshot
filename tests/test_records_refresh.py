from src.records_refresh import replace_saved_record
from src.vijay_finance import project_vijay_records


def test_saved_invoice_replaces_old_preview_row_without_page_reload():
    old = {'request_number': 'REQ-1', 'created_by': 'Vijay', 'report_scope': 'DTR',
           'invoice_number': 'OLD', 'dtr_data': {'LR No.': 'OLD'}, 'revenue': 100}
    saved = {**old, 'invoice_number': 'NEW', 'dtr_data': {'LR No.': 'NEW'}}
    rows, fresh = replace_saved_record([old], 'REQ-1', lambda number: saved, project_vijay_records)
    assert fresh['invoice_number'] == 'NEW'
    assert rows[0]['invoice_number'] == 'NEW'
    assert rows[0]['dtr_data']['LR No.'] == 'NEW'
    assert old['invoice_number'] == 'OLD'


def test_shyam_edit_to_another_users_trip_refreshes_the_shared_preview():
    old = {'request_number': 'REQ-2', 'created_by': 'Ajit', 'report_scope': 'DTR',
           'invoice_number': 'OLD', 'dtr_data': {'LR No.': 'LR-1'}}
    saved = {**old, 'invoice_number': 'CORRECTED'}
    rows, fresh = replace_saved_record([old], 'REQ-2', lambda number: saved, project_vijay_records)
    assert rows[0]['invoice_number'] == fresh['invoice_number'] == 'CORRECTED'
