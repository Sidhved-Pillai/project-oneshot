import pytest
from streamlit.testing.v1 import AppTest

from src import shyam_records_design
from src.access_control import can_delete_record
from src.record_integrity import can_edit_record


@pytest.mark.parametrize('member', ['sid', 'nikhat', 'vijay', 'ajit', 'nitish', 'gopal', 'manish'])
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
