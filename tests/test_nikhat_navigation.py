import ast
from pathlib import Path
from types import SimpleNamespace


def test_nikhat_tabs_exclude_new_entry_and_include_pending_payments():
    tree = ast.parse(Path('app.py').read_text())
    navigation = next(node for node in tree.body if isinstance(node, ast.If)
                      and any(isinstance(child, ast.Assign) and any(isinstance(target, ast.Name)
                          and target.id == 'new_tab' for target in child.targets)
                          for child in ast.walk(node))
                      and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
                          and child.func.attr == 'tabs' for child in ast.walk(node)))
    labels = []
    def tabs(names):
        labels.extend(names)
        return list(names)
    namespace = {'current_user':'Nikhat', 'st':SimpleNamespace(tabs=tabs), 'PENDING_PAYMENT_USERS':{'Nikhat'}}
    exec(compile(ast.Module(body=[navigation], type_ignores=[]), 'navigation', 'exec'), namespace)
    assert labels == ['Direct Expenses','Records','Pending Payments','Generate Reports','Logs']
    assert namespace['new_tab'] is None


def test_nikhat_bill_access_with_refreshed_cached_store(tmp_path):
    from src.payment_access_v2 import PENDING_PAYMENT_USERS
    from src.records_store_v25 import RequestStore
    from src.pending_payments_v10 import render_pending_payments
    from tests.test_pending_payments import trip
    assert 'Nikhat' in PENDING_PAYMENT_USERS
    store = RequestStore(f'sqlite:///{tmp_path / "nikhat.db"}')
    assert store.list_balance_bills('Nikhat') == []
    assert store.pending_upi_profiles('Nikhat') == {}
    number = trip(store)
    assert store.send_pending_payments({number:store.get(number)['updated_at']}, 'balance', 'Nikhat') == 1
    bills = store.list_balance_bills('Nikhat')
    assert len(bills) == 1
    assert store.get_balance_bill(bills[0]['id'], 'Nikhat')['rows'][0]['request_number'] == number
