from pathlib import Path


def test_streamlit_is_pinned_for_operator_browser_compatibility():
    requirements = (Path(__file__).parents[1] / "requirements.txt").read_text()

    assert "streamlit==1.50.0" in requirements
    assert "streamlit>=" not in requirements
