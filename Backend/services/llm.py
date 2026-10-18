"""Provider-agnostic LLM access with an ordered fallback chain.

SafeZone calls a model in exactly one place -- turning a free-text report into
structured fields (``services/extract.py``). This module is the boundary
around that call, and it exists for one reason: AGENTS.md 12 says swapping
providers when one rate-limits *during the event* must be a config change, not
a deploy.

Three properties matter:

* **Ordered fallback.** ``LLM_PROVIDERS`` is tried in order. A provider with
  no key is skipped silently rather than counted as a failure, so a half-filled
  ``.env`` degrades to whatever is actually configured.
* **One interface.** DeepSeek, Groq and Gemini all expose OpenAI-compatible
  chat completions, so a single client covers all three and adding a fourth is
  a row in :data:`PROVIDERS`, not a new code path.
* **Failure is normal.** Every provider being down is an expected state, not an
  exception to be surprised by. Callers catch :class:`LLMUnavailable` and fall
  back to deterministic keyword extraction; the help ladder never waits on a
  model.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core import config

logger = logging.getLogger("safezone.llm")

DEFAULT_TIMEOUT_S = 15


class LLMUnavailable(RuntimeError):
    """Raised when no configured provider could answer.

    Callers are expected to handle this, not propagate it. An emergency report
    must still be accepted, ranked and dispatched with the model offline.
    """


@dataclass(frozen=True)
class Provider:
    """One OpenAI-compatible endpoint.

    ``base_url`` is ``None`` for OpenAI itself, where the SDK default applies.
    """

    name: str
    base_url: Optional[str]
    default_model: str


# Gemini is reached through its OpenAI-compatibility endpoint so that one
# client and one request shape cover every provider here.
PROVIDERS: Dict[str, Provider] = {
    "deepseek": Provider(
        name="deepseek",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
    ),
    "groq": Provider(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        default_model="llama-3.3-70b-versatile",
    ),
    # Default model names go stale on the provider's schedule, not ours --
    # Google retired gemini-2.0-flash while this was being built. When a
    # provider answers 404 for its model, `python -m scripts.verify_setup`
    # lists what the key can actually reach and prints the GEMINI_MODEL line
    # to paste into .env. Setting that env var overrides this default.
    "gemini": Provider(
        name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        default_model="gemini-flash-latest",
    ),
    "openai": Provider(name="openai", base_url=None, default_model="gpt-4o-mini"),
    "openrouter": Provider(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-4o-mini",
    ),
}


def credentials(name: str) -> tuple[str, str]:
    """Return ``(api_key, model)`` for a provider, or ``("", "")`` if unusable.

    Per-provider settings (``DEEPSEEK_API_KEY``) win. The single-provider
    ``LLM_API_KEY`` / ``LLM_MODEL`` pair is honoured as a fallback when it
    names this provider, so an existing ``.env`` keeps working untouched.
    """
    provider = PROVIDERS.get(name)
    if provider is None:
        return "", ""

    prefix = name.upper()
    api_key = (getattr(config, f"{prefix}_API_KEY", "") or "").strip()
    model = (getattr(config, f"{prefix}_MODEL", "") or "").strip()

    if config.LLM_PROVIDER == name:
        api_key = api_key or config.LLM_API_KEY
        model = model or config.LLM_MODEL

    if not api_key:
        return "", ""
    return api_key, model or provider.default_model


def provider_chain() -> List[Provider]:
    """Configured providers that have a key, in the order they will be tried."""
    chain: List[Provider] = []
    for name in config.LLM_PROVIDERS:
        provider = PROVIDERS.get(name)
        if provider is None:
            logger.warning("Unknown LLM provider %r in LLM_PROVIDERS; skipping", name)
            continue
        api_key, _model = credentials(name)
        if not api_key:
            continue
        chain.append(provider)
    return chain


def available() -> bool:
    """True when at least one provider could be called."""
    return bool(provider_chain())


def complete_json(
    system_prompt: str,
    user_prompt: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_S,
) -> Dict[str, Any]:
    """Ask the first working provider for a single JSON object.

    Raises:
        LLMUnavailable: when nothing is configured, or every provider failed.
    """
    chain = provider_chain()
    if not chain:
        raise LLMUnavailable(
            "No LLM provider is configured. Set one of DEEPSEEK_API_KEY, "
            "GROQ_API_KEY or GEMINI_API_KEY, or LLM_API_KEY with LLM_PROVIDER."
        )

    failures: List[str] = []
    for provider in chain:
        api_key, model = credentials(provider.name)
        try:
            content = _chat(provider, api_key, model, system_prompt, user_prompt, timeout)
            parsed = json.loads(content)
        except Exception as exc:  # noqa: BLE001 - any provider failure is routine
            # The key itself must never reach a log line.
            logger.warning("LLM provider %s failed: %s", provider.name, exc)
            failures.append(f"{provider.name}: {exc}")
            continue

        if not isinstance(parsed, dict):
            logger.warning("LLM provider %s returned %s, not an object", provider.name, type(parsed).__name__)
            failures.append(f"{provider.name}: response was not a JSON object")
            continue

        logger.info("LLM extraction served by %s (%s)", provider.name, model)
        return parsed

    raise LLMUnavailable("Every LLM provider failed -- " + "; ".join(failures))


def _chat(
    provider: Provider,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    timeout: int,
) -> str:
    """One chat completion, returning the raw message content."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=provider.base_url)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        timeout=timeout,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("empty response")
    return content


def complete_chat(
    messages: List[Dict[str, Any]],
    *,
    temperature: float = 0.3,
    max_tokens: int = 500,
    timeout: int = DEFAULT_TIMEOUT_S,
    provider: Optional[str] = None,
    api_key: str = "",
    model: str = "",
) -> str:
    """Ask the first working provider for free text, given a message list.

    The sibling of :func:`complete_json`. That one exists for the report
    extraction on the critical path, where the answer must be a JSON object and
    the temperature is zero. This one serves the website assistant, which is
    *not* on the critical path: nobody is dispatched because of what it says,
    so prose and a little warmth are fine.

    It shares the provider chain deliberately. The assistant going quiet
    because Gemini rate-limited during a demo is avoidable when DeepSeek and
    Groq are already configured and idle.

    ``messages`` is OpenAI shaped -- ``{"role": ..., "content": ...}`` -- where
    content may be a string or the multimodal parts list. Providers without
    vision fail a parts list and the chain moves on, which is the same path as
    any other provider failure.

    Raises:
        LLMUnavailable: when nothing is configured, or every provider failed.
    """
    # A caller may pin one provider with a key of its own. The website
    # assistant does: a separate key means a scraper that burns the chat quota
    # cannot take report extraction down with it, and extraction is the one
    # that sits near the critical path.
    if api_key and provider:
        pinned = PROVIDERS.get(provider)
        if pinned is None:
            raise LLMUnavailable(f"Unknown provider {provider!r}")
        chain = [pinned]
        overrides: Dict[str, tuple[str, str]] = {
            pinned.name: (api_key, model or pinned.default_model)
        }
    else:
        chain = provider_chain()
        overrides = {}

    if not chain:
        raise LLMUnavailable(
            "No LLM provider is configured. Set one of DEEPSEEK_API_KEY, "
            "GROQ_API_KEY or GEMINI_API_KEY, or LLM_API_KEY with LLM_PROVIDER."
        )

    failures: List[str] = []
    for candidate in chain:
        key, name = overrides.get(candidate.name) or credentials(candidate.name)
        try:
            from openai import OpenAI

            client = OpenAI(api_key=key, base_url=candidate.base_url)
            response = client.chat.completions.create(
                model=name,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=messages,
                timeout=timeout,
            )
            content = (response.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001 - any provider failure is routine
            # The key itself must never reach a log line.
            logger.warning("LLM provider %s failed: %s", candidate.name, exc)
            failures.append(f"{candidate.name}: {exc}")
            continue

        if not content:
            failures.append(f"{candidate.name}: empty response")
            continue

        logger.info("Chat served by %s (%s)", candidate.name, name)
        return content

    raise LLMUnavailable("Every LLM provider failed -- " + "; ".join(failures))
