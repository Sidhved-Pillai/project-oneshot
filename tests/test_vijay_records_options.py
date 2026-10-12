import ast
from pathlib import Path


def test_vijay_bulk_import_and_pending_matching_are_removed():
    tree = ast.parse(Path('app.py').read_text())
    labels = {node.args[0].value for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr == 'expander' and node.args
              and isinstance(node.args[0], ast.Constant)}
    assert 'Import Excel' not in labels
    assert 'Upload Pending Invoices & Match' not in labels
    source = ast.unparse(tree)
    assert 'vijay_pending_invoice_uploads' not in source
    assert 'confirm_vijay_records_import' not in source
    assert "current_user in {'Manish', 'Vijay'}" in source
    assert "'Download Excel'" in source
