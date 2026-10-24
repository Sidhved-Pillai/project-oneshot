import ast
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_record_filters_apply_together_and_reject_invalid_dates():
    app = AppTest.from_string('''
import datetime as dt
import streamlit as st
from src.batched_records import render_filters
filters = render_filters([], 'Sid', dt.date(2026,10,14))
st.write('APPLIED: ' + filters['record_type'])
''').run()
    assert not app.exception
    app.selectbox[0].select('Direct Expenses')
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state['applied_records_filters_Sid']['record_type'] == 'Direct Expenses'
    import datetime as dt
    app.date_input[0].set_value(dt.date(2026,10,20))
    app.button[0].click().run()
    assert not app.exception
    assert app.error
    assert app.session_state['applied_records_filters_Sid']['start'] == dt.date(2026,10,1)


def trip_app(user):
    tree = ast.parse(Path('app.py').read_text())
    imports = [n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))]
    definitions = [n for n in tree.body if isinstance(n,ast.FunctionDef) and not n.decorator_list]
    constants = [n for n in tree.body if isinstance(n,ast.Assign) and
                 any(isinstance(t,ast.Name) and t.id in {'PAYMENT_FIELDS','BRANCHES'} for t in n.targets)]
    source = '\n'.join(ast.unparse(n) for n in imports + constants + definitions)
    source += f"\ncurrent_user = {user!r}\n"
    source += '''
normalization_rows = []
business_memory = {}
historical_business_memory = {}
KNOWN_COMPANIES = []
KNOWN_LOCATIONS = []
st.session_state.setdefault('test_branch','Pune' if current_user != 'Vijay' else 'Andheri')
st.session_state.setdefault('test_ownership_type','Outside')
st.session_state.setdefault('test_vehicle_number','MH14JL9818' if current_user != 'Vijay' else 'MH17AG4504')
values = trip_form('test', {}, BRANCHES, simplified=current_user == 'Manish')
st.session_state['test_returned_values'] = values
'''
    return AppTest.from_string(source).run()


def test_entry_preserves_original_controls_without_extra_buttons():
    for user in ('Nitish','Vijay','Manish','Ashok'):
        app = trip_app(user)
        assert not app.exception
        assert not any(button.label in {'Calculate payments','Apply trip details'} for button in app.button)


def test_payment_calculations_update_without_a_calculate_button():
    app = trip_app('Nitish')
    rtgs = next(widget for widget in app.number_input if widget.label == 'RTGS (₹)')
    rtgs.set_value(1250).run()
    assert not app.exception
    values = app.session_state['test_returned_values']
    assert values['rtgs_advance'] == 1250


def test_vijay_uses_fixed_own_vehicle_expense_workflow():
    app = trip_app('Vijay')
    assert not app.exception
    ownership = next(widget for widget in app.selectbox if widget.label == 'Own or outside')
    assert ownership.value == 'Own'
    assert ownership.disabled
    labels = {widget.label for widget in app.number_input}
    assert {'UPI (₹)', 'Diesel (₹)', 'Cash (₹)', 'RTGS (₹)', 'Toll Expense (₹)', 'Billtee (₹)'} <= labels
    assert 'Transporter freight (₹)' not in labels
    assert 'Repairs & Maintenance (₹)' not in labels
    assert {'Total Expense', 'Total Advance'} <= {metric.label for metric in app.metric}


def test_order_controls_remain_beside_live_records_not_in_filter_form():
    form_source = Path('src/batched_records.py').read_text()
    assert "selectbox('Record order'" not in form_source
    assert "st.toggle('Show Records without Invoice Evidence'" not in form_source
    app_source = Path('app.py').read_text()
    assert 'sort_arrow = live_sort.segmented_control(' in app_source
    assert '@st.fragment\ndef render_new_entry()' in app_source


def test_ajit_has_all_filters_and_identifiers_are_batched():
    app = AppTest.from_string('''
import datetime as dt
import streamlit as st
from src.batched_records_v5 import render_filters
filters = render_filters([{'invoice_number':'GST/GST/1087', 'dtr_data':{'LR No.':'UTPL-139'}}], 'Ajit', dt.date(2026,10,18))
''').run()
    assert not app.exception
    assert {'Vehicle placed by', 'Vehicle no.', 'Own or outside'} <= {w.label for w in app.selectbox}
    assert next(w for w in app.selectbox if w.label == 'LR No.').options == ['All', 'UTPL-139']
    next(w for w in app.selectbox if w.label == 'LR No.').select('UTPL-139')
    next(w for w in app.selectbox if w.label == 'Invoice No.').select('GST/GST/1087')
    assert 'applied_records_filters_Ajit' not in app.session_state
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state['applied_records_filters_Ajit']['lr_number'] == 'UTPL-139'
    assert app.session_state['applied_records_filters_Ajit']['invoice_number'] == 'GST/GST/1087'
    app.selectbox[0].select('Direct Expenses')
    app.button[0].click().run()
    assert not app.exception
    assert {'By Amount', 'Heading'} <= {w.label for w in app.selectbox}


def test_identifier_filters_preserve_invoice_serials_and_support_json():
    from src.batched_records_v4 import filter_identifiers
    rows = [
        {'invoice_number': 'GST/GST/1087/26-27', 'dtr_data': {'LR No.': 'UTPL-139'}},
        {'dtr_data': '{"LR No.": "UTPL-118", "Invoice No.": "GST/GST/0885/26-27"}'},
    ]
    assert filter_identifiers(rows, {}) == rows
    assert filter_identifiers(rows, {'lr_number': ' utpl-139 '}) == rows[:1]
    assert filter_identifiers(rows, {'invoice_number': 'gst/gst/0885'}) == rows[1:]
    assert filter_identifiers(rows, {'lr_number': '139', 'invoice_number': '0885'}) == []


def test_direct_expense_has_only_save_and_add_another():
    tree = ast.parse(Path('app.py').read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'render_direct_expenses')
    labels = [n.args[0].value for n in ast.walk(function) if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute) and n.func.attr == 'button'
              and n.args and isinstance(n.args[0], ast.Constant)]
    assert labels.count('Save & Add Another') == 1
    assert 'Save direct expense' not in labels


def test_ajit_can_apply_vehicle_filters_repeatedly_without_refresh():
    app = AppTest.from_string('''
import datetime as dt
import streamlit as st
from src.batched_records_v6 import render_filters
rows = [{'vehicle_number':v} for v in ['MH12AB1234','MH14CD5678','MH01EF9999']]
filters = render_filters(rows, 'Ajit', dt.date(2026,10,21))
st.write('RESULT: ' + filters['vehicle'])
if st.button('Unrelated rerun'):
    st.write('Refreshed')
''').run()
    for vehicle in ('MH12AB1234','MH14CD5678','MH01EF9999','All','MH14CD5678'):
        next(w for w in app.selectbox if w.label=='Vehicle no.').select(vehicle)
        next(w for w in app.button if w.label=='Apply Filters').click().run()
        assert not app.exception
        assert app.session_state['applied_records_filters_Ajit']['vehicle']==vehicle
        assert next(w for w in app.selectbox if w.label=='Vehicle no.').value==vehicle
        next(w for w in app.button if w.label=='Unrelated rerun').click().run()
        assert not app.exception
        assert next(w for w in app.selectbox if w.label=='Vehicle no.').value==vehicle
