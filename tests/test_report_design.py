import pandas as pd

from src.report_design import pnl_table_html, rtgs_search_options


def test_rtgs_suggestions_preserve_invoice_ids_and_bank_leading_zeroes():
    options = rtgs_search_options([{'transporter_name': 'Jadhav Transport',
        'vehicle_number': 'MH12YQ6622', 'invoice_number': 'GST/GST/1295/26-27, TEST-2',
        'beneficiary_name': 'Jadhav Transport'}])
    assert 'Jadhav Transport' in options
    assert 'MH12YQ6622' in options
    assert 'GST/GST/1295/26-27' in options
    assert 'TEST-2' in options
    assert options.count('Jadhav Transport') == 1


def test_pnl_presentation_keeps_columns_values_and_total_for_each_format():
    for label in ['Branch', 'Vehicle No.']:
        frame = pd.DataFrame([{label: 'Wada', 'Revenue': 1000.5, 'Expense': 1100.5, 'Profit': -100},
                              {label: 'Total', 'Revenue': 1000.5, 'Expense': 1100.5, 'Profit': -100}])
        before = frame.copy(deep=True)
        html = pnl_table_html(frame)
        assert '<th>' + label + '</th>' in html
        assert 'pnl-total' in html and '1,000.50' in html and '100.00' in html
        pd.testing.assert_frame_equal(frame, before)
