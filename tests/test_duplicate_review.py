from pathlib import Path

from src.duplicate_review import duplicate_review_frame, selected_duplicate_numbers


def test_duplicate_grid_details_are_unselected_and_selection_uses_record_ids():
    rows = [
        {'request_number':'A','report_scope':'Expense','amount':100,'created_by':'Shyam',
         'dtr_data':'{"LR No.": "LR1", "Billtee": 20}'},
        {'request_number':'B','invoice_number':'INV2','revenue':200,'dtr_data':{}},
    ]
    frame = duplicate_review_frame(rows)
    assert not frame['Select'].any()
    assert frame.iloc[0]['Type'] == 'Direct Expense'
    assert frame.iloc[0]['LR No.'] == 'LR1'
    assert frame.iloc[0]['Billtee'] == 20
    assert selected_duplicate_numbers(frame, ['A','B']) == []
    frame.loc[1,'Select'] = True
    assert selected_duplicate_numbers(frame.iloc[::-1], ['A','B']) == ['B']
    assert selected_duplicate_numbers(frame, ['A']) == []


def test_duplicate_grid_only_edits_selection_and_shyam_has_no_cross_icon():
    source = Path('app.py').read_text()
    assert "disabled=[col for col in duplicate_frame if col != 'Select']" in source
    assert 'records_duplicate_grid_' in source
    assert 'records_delete_selection_' not in source
    assert "actions['received'].button('', icon=':material/check:'" in source
    assert "received_undo_" not in source
    assert 'st-key-received_done_' in source
