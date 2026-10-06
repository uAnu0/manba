"""Gemini is the default provider wherever a Gemini key is available; OpenRouter only when it is the one key there is."""
import pytest

from app.services import llm_extractor as L


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for v in ("LLM_PROVIDER", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "EMBED_PROVIDER", "LLM_MODEL"):
        monkeypatch.delenv(v, raising=False)
    L.set_request_llm(None, None, None)
    yield
    L.set_request_llm(None, None, None)


def test_server_with_both_keys_defaults_to_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("OPENROUTER_API_KEY", "o")
    assert L.server_default_provider() == "google" and L.provider_for() == "google"


def test_server_with_only_openrouter_keeps_working(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "o")
    assert L.server_default_provider() == "openrouter" and L.provider_for() == "openrouter"


def test_a_gemini_key_brought_in_settings_makes_gemini_the_default(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "o")
    L.set_request_llm(None, None, "my-gemini-key")
    assert L.provider_for() == "google"


def test_a_person_with_only_an_openrouter_key_gets_openrouter(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    L.set_request_llm(None, "my-openrouter-key", None)
    assert L.provider_for() == "openrouter"


def test_explicit_choices_still_win(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    assert L.provider_for() == "openrouter"
    monkeypatch.delenv("LLM_PROVIDER")
    L.set_request_llm("openrouter", None, None)
    assert L.provider_for() == "openrouter"
    L.set_request_llm(None, None, None)
    monkeypatch.setenv("EMBED_PROVIDER", "openrouter")
    assert L.provider_for("EMBED") == "openrouter" and L.provider_for("LLM") == "google"


def test_openrouter_model_names_from_the_environment_are_ignored_on_a_gemini_default(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o-mini, google:gemini-3.1-flash-lite")
    assert L.env_models("LLM_MODEL") == ["google:gemini-3.1-flash-lite"]
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    assert L.env_models("LLM_MODEL") == ["openai/gpt-4o-mini", "google:gemini-3.1-flash-lite"]
