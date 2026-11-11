import pytest

from app.services import ledger_service


@pytest.fixture(autouse=True)
def isolated_anchor(tmp_path, monkeypatch):
    """Every test gets its own anchor file, so tests never see each other's heads."""
    path = tmp_path / "ledger_anchor.jsonl"
    monkeypatch.setattr(ledger_service, "ANCHOR_PATH", str(path))
    return path
