from src.sid_entry_design import render_sid_header


def test_header_shows_signed_in_name_and_initial(monkeypatch, tmp_path):
    logo = tmp_path / 'logo.png'
    logo.write_bytes(b'logo')
    rendered = []
    monkeypatch.setattr('src.sid_entry_design.st.markdown',
                        lambda html, **kwargs: rendered.append(html))
    render_sid_header(logo, 'Manish')
    assert 'aria-label="Signed in as Manish"' in rendered[0]
    assert 'class="sid-user-avatar" aria-hidden="true">M</span>' in rendered[0]
    assert 'class="sid-user-name">Manish</span>' in rendered[0]
    render_sid_header(logo, 'Nikhil')
    assert 'class="sid-user-name">Nikhil</span>' in rendered[1]
