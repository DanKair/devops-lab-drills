import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Keep config/progress out of the real ~/.labdrills during tests."""
    monkeypatch.setenv("LAB_DRILLS_HOME", str(tmp_path / "home"))
    for key in ("LAB_DRILLS_LABS", "LAB_GITLAB_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    from labctl import catalog
    catalog.all_labs.cache_clear()
    catalog.tracks.cache_clear()
    yield
    catalog.all_labs.cache_clear()
    catalog.tracks.cache_clear()
