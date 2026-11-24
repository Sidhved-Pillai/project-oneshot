import pytest
from streamlit.testing.v1 import AppTest

from src import shyam_records_design
from src.access_control import can_delete_record
from src.record_integrity import can_edit_record
from src.company_catalog import COMPANIES, NEEDS_REVIEW, NEEDS_COMPANY_REVIEW


@pytest.mark.parametrize('member', ['sid', 'nikhil', 'nikhat', 'vijay', 'ajit', 'nitish', 'gopal', 'manish', 'ashok'])
def test_records_styles_are_scoped_to_member(monkeypatch, member):
    styles = []
    monkeypatch.setattr(shyam_records_design.st, 'markdown', lambda value, **kwargs: styles.append(value))

    shyam_records_design.styles(member)

    assert len(styles) == 1
    assert f'.st-key-{member}_records_table' in styles[0]
    assert f'.st-key-{member}_records_filters' in styles[0]
    assert '.st-key-shyam_records_table' not in styles[0]


@pytest.mark.parametrize('member', ['Nikhat', 'Vijay', 'Ajit', 'Manish'])
def test_designed_filters_keep_direct_expense_controls(member):
    app = AppTest.from_string(f'''
import datetime as dt
from src.batched_records import render_filters
render_filters([{{'report_scope': 'Expense', 'amount': 500, 'dtr_data': {{'Salary': 500}}}}],
               {member!r}, dt.date(2026, 11, 21))
''').run()
    assert not app.exception
    next(widget for widget in app.selectbox if widget.label == 'Record Type').select('Direct Expenses')
    next(widget for widget in app.button if widget.label == 'Apply Filters').click().run()
    assert not app.exception
    assert any(widget.label == 'By Amount' for widget in app.selectbox)
    assert any(widget.label == 'Heading' for widget in app.selectbox)


def test_pune_records_keep_nitish_and_gopal_action_rules():
    nitish_row = {'created_by': 'Nitish', 'branch': 'Pune'}
    gopal_row = {'created_by': 'Gopal', 'branch': 'Pune'}
    assert can_delete_record('Nitish', nitish_row)
    assert can_delete_record('Nitish', gopal_row)
    assert not can_delete_record('Gopal', gopal_row)
    assert can_edit_record('Nitish', nitish_row)
    assert not can_edit_record('Nitish', gopal_row)
    assert can_edit_record('Gopal', gopal_row)
    assert not can_edit_record('Gopal', nitish_row)


def test_ashok_records_filters_keep_his_restricted_controls():
    app = AppTest.from_string('''
import datetime as dt
from src.batched_records import render_filters
render_filters([{'report_scope': 'Expense', 'amount': 500, 'dtr_data': {'Salary': 500}}],
               'Ashok', dt.date(2026, 11, 21))
''').run()
    assert not app.exception
    labels = {widget.label for widget in app.selectbox}
    assert 'Vehicle no.' in labels
    assert 'Vehicle placed by' not in labels
    assert 'Own or outside' not in labels
    next(widget for widget in app.selectbox if widget.label == 'Record Type').select('Direct Expenses')
    next(widget for widget in app.button if widget.label == 'Apply Filters').click().run()
    assert not app.exception
    assert {'By Amount', 'Heading'} <= {widget.label for widget in app.selectbox}


@pytest.mark.parametrize('member', ['Sid', 'Nikhil'])
def test_records_branch_and_placer_filters_use_clean_options(member):
    app = AppTest.from_string(f'''
import datetime as dt
from src.batched_records import render_filters
render_filters([
    {{'branch': 'Vadodra', 'company_name': 'Saint Gobain', 'dtr_data': {{'Veh Placed by': 'UBIQUITY TRANSTECH PVT LTD'}}}},
    {{'branch': 'Pune', 'company_name': 'Bisleri', 'dtr_data': {{'Veh Placed by': 'Nit'}}}},
], {member!r}, dt.date(2026, 11, 24))
''').run()
    assert not app.exception
    options = {widget.label: widget.options for widget in app.selectbox}
    assert options['Branch'] == ['All', 'Pune', 'Vadodara']
    assert options['Company Name'] == ['All', *COMPANIES, NEEDS_REVIEW, NEEDS_COMPANY_REVIEW]
    assert options['Vehicle placed by'] == [
        'All', 'Nitish Jha', 'Manish Jha', 'Gopal', 'Shyam',
        'Ajit Thakur', 'Ashok', 'Vijay',
    ]
    app.selectbox(key=f'records_filter_draft_{member}_branch').select('Pune')
    app.selectbox(key=f'records_filter_draft_{member}_company').select('Bisleri International Private Limited')
    app.selectbox(key=f'records_filter_draft_{member}_placer').select('Nitish Jha')
    next(widget for widget in app.button if widget.label == 'Apply Filters').click().run()
    assert not app.exception
    assert app.session_state[f'applied_records_filters_{member}']['branch'] == 'Pune'
    assert app.session_state[f'applied_records_filters_{member}']['company'] == 'Bisleri International Private Limited'
    assert app.session_state[f'applied_records_filters_{member}']['placer'] == 'Nitish Jha'
