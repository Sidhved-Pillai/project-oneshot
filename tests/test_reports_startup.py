"""Reports must render without an entry-draft browser handshake for Sid."""
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize('entrypoint', ['app.py', 'recovery_app.py'])
def test_sid_reports_render_without_browser_draft_component(tmp_path, monkeypatch, entrypoint):
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///' + str(tmp_path / 'startup.db'))
    app = AppTest.from_file(entrypoint, default_timeout=30)
    app.session_state['authenticated'] = True
    app.session_state['authenticated_user'] = 'Sid'
    app.session_state['is_special_member'] = True
    with patch('src.entry_drafts.entry_draft_bridge', side_effect=AssertionError('No entry forms for Sid')):
        app.run()
    assert not app.exception
    reports = next(tab for tab in app.tabs if tab.label == 'Generate Reports')
    assert any('Generate Reports' in item.value for item in reports.markdown)
    assert reports.date_input
