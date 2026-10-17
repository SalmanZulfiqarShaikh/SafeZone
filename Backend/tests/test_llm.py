"""The provider fallback chain.

The behaviour that matters during the event: DeepSeek rate-limits, Groq picks
it up, nobody notices. And when every provider is down, the caller gets a
clean :class:`LLMUnavailable` so extraction can fall back to keywords instead
of a report being lost.
"""

import json

import pytest

from core import config
from services import extract, llm


@pytest.fixture(autouse=True)
def clean_providers(monkeypatch):
    """Start every test with no keys, so nothing leaks in from the shell."""
    for name in ("DEEPSEEK", "GROQ", "GEMINI", "OPENAI", "OPENROUTER"):
        monkeypatch.setattr(config, f"{name}_API_KEY", "", raising=False)
        monkeypatch.setattr(config, f"{name}_MODEL", "", raising=False)
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    monkeypatch.setattr(config, "LLM_MODEL", "")
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "LLM_PROVIDERS", ["deepseek", "groq", "gemini"])


def fake_chat(answers):
    """Build a ``_chat`` stand-in driven by a {provider: result} mapping.

    A value that is an exception is raised; anything else is returned.
    """
    calls = []

    def _chat(provider, api_key, model, system_prompt, user_prompt, timeout):
        calls.append((provider.name, model))
        result = answers[provider.name]
        if isinstance(result, Exception):
            raise result
        return result

    return _chat, calls


# ─── Chain construction ────────────────────────────────────────────────────


def test_no_keys_means_no_providers():
    assert llm.provider_chain() == []
    assert llm.available() is False


def test_only_providers_with_a_key_are_in_the_chain(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "groq-key")

    assert [p.name for p in llm.provider_chain()] == ["groq"]
    assert llm.available() is True


def test_chain_order_follows_configuration(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "a")
    monkeypatch.setattr(config, "GROQ_API_KEY", "b")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "c")

    assert [p.name for p in llm.provider_chain()] == ["deepseek", "groq", "gemini"]

    monkeypatch.setattr(config, "LLM_PROVIDERS", ["gemini", "deepseek"])
    assert [p.name for p in llm.provider_chain()] == ["gemini", "deepseek"]


def test_unknown_provider_names_are_skipped(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDERS", ["nonsense", "groq"])
    monkeypatch.setattr(config, "GROQ_API_KEY", "b")

    assert [p.name for p in llm.provider_chain()] == ["groq"]


def test_single_provider_settings_still_work(monkeypatch):
    """An existing .env with only LLM_API_KEY/LLM_PROVIDER must keep working."""
    monkeypatch.setattr(config, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(config, "LLM_API_KEY", "legacy-key")
    monkeypatch.setattr(config, "LLM_MODEL", "legacy-model")

    assert llm.credentials("groq") == ("legacy-key", "legacy-model")
    assert [p.name for p in llm.provider_chain()] == ["groq"]


def test_provider_specific_key_wins_over_the_generic_one(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(config, "LLM_API_KEY", "legacy-key")
    monkeypatch.setattr(config, "GROQ_API_KEY", "specific-key")

    key, _model = llm.credentials("groq")
    assert key == "specific-key"


def test_model_defaults_per_provider(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "a")

    _key, model = llm.credentials("deepseek")
    assert model == llm.PROVIDERS["deepseek"].default_model


# ─── Fallback behaviour ────────────────────────────────────────────────────


def test_first_working_provider_answers(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "a")
    monkeypatch.setattr(config, "GROQ_API_KEY", "b")
    _chat, calls = fake_chat({"deepseek": json.dumps({"category": "flood"})})
    monkeypatch.setattr(llm, "_chat", _chat)

    assert llm.complete_json("sys", "user") == {"category": "flood"}
    assert [name for name, _model in calls] == ["deepseek"]


def test_failure_falls_through_to_the_next_provider(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "a")
    monkeypatch.setattr(config, "GROQ_API_KEY", "b")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "c")
    _chat, calls = fake_chat(
        {
            "deepseek": RuntimeError("429 rate limited"),
            "groq": json.dumps({"category": "fire"}),
        }
    )
    monkeypatch.setattr(llm, "_chat", _chat)

    assert llm.complete_json("sys", "user") == {"category": "fire"}
    assert [name for name, _model in calls] == ["deepseek", "groq"]


def test_unparseable_json_counts_as_a_failure(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "a")
    monkeypatch.setattr(config, "GROQ_API_KEY", "b")
    _chat, calls = fake_chat(
        {"deepseek": "not json at all", "groq": json.dumps({"category": "medical"})}
    )
    monkeypatch.setattr(llm, "_chat", _chat)

    assert llm.complete_json("sys", "user") == {"category": "medical"}
    assert [name for name, _model in calls] == ["deepseek", "groq"]


def test_a_json_array_is_rejected_not_returned(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "a")
    _chat, _calls = fake_chat({"deepseek": json.dumps([1, 2, 3])})
    monkeypatch.setattr(llm, "_chat", _chat)

    with pytest.raises(llm.LLMUnavailable):
        llm.complete_json("sys", "user")


def test_every_provider_failing_raises_llm_unavailable(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "a")
    monkeypatch.setattr(config, "GROQ_API_KEY", "b")
    _chat, _calls = fake_chat(
        {"deepseek": RuntimeError("down"), "groq": RuntimeError("also down")}
    )
    monkeypatch.setattr(llm, "_chat", _chat)

    with pytest.raises(llm.LLMUnavailable) as excinfo:
        llm.complete_json("sys", "user")

    assert "deepseek" in str(excinfo.value)
    assert "groq" in str(excinfo.value)


def test_nothing_configured_raises_a_helpful_error():
    with pytest.raises(llm.LLMUnavailable) as excinfo:
        llm.complete_json("sys", "user")

    assert "DEEPSEEK_API_KEY" in str(excinfo.value)


# ─── Integration with extraction ───────────────────────────────────────────


def test_extraction_falls_back_to_keywords_when_every_provider_is_down(monkeypatch):
    """The whole point: a dead model never costs us a report."""
    monkeypatch.setattr(config, "MOCK_MODE", False)
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "a")
    _chat, _calls = fake_chat({"deepseek": RuntimeError("down")})
    monkeypatch.setattr(llm, "_chat", _chat)

    result = extract.extract_report("there is a fire in my kitchen in Gulshan")

    assert result["category"] == "fire"
    assert result["zone_guess"] == "gulshan"


def test_extraction_uses_the_model_when_one_answers(monkeypatch):
    monkeypatch.setattr(config, "MOCK_MODE", False)
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "a")
    _chat, _calls = fake_chat(
        {
            "deepseek": json.dumps(
                {
                    "category": "trapped",
                    "urgency": "critical",
                    "location_text": "Gulshan 13-D",
                    "vulnerability": {"elderly": True},
                }
            )
        }
    )
    monkeypatch.setattr(llm, "_chat", _chat)

    result = extract.extract_report("stuck on the roof")

    assert result["category"] == "trapped"
    assert result["urgency"] == "critical"
    assert result["vulnerability"]["elderly"] is True
    # Unstated fields stay unknown, never False.
    assert result["vulnerability"]["alone"] is None


def test_mock_mode_never_calls_a_provider(monkeypatch):
    monkeypatch.setattr(config, "MOCK_MODE", True)
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "a")

    def explode(*_args, **_kwargs):
        raise AssertionError("MOCK_MODE must not reach a provider")

    monkeypatch.setattr(llm, "_chat", explode)

    assert extract.extract_report("there is a fire")["category"] == "fire"
