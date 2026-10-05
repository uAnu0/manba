"""Common modern spellings of Quranic words still match, and the AI status check reports instead of failing."""
import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.services.verifier import verify_segment


def test_modern_spellings_match_the_mushaf():
    assert verify_segment("ولا تقربوا الزنا").status == "verified"
    kursi = verify_segment("ولا يؤوده حفظهما وهو العلي العظيم")
    assert kursi.status == "verified" and kursi.source.number.startswith("2:255")


def test_changed_word_still_differs():
    assert verify_segment("وأحل الله البيع وحرم الزنا").status != "verified"


def test_llm_check_reports_without_raising(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from app.config import settings
    monkeypatch.setattr(settings, "api_access_token", "")
    r = TestClient(app).get("/api/llm-check")
    assert r.status_code == 200 and r.json()["ok"] is False and "key" in r.json()["error"].lower()
