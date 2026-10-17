"""Check SafeZone against the real services. Read-only. Sends nothing.

Everything in ``tests/`` runs against a fake database and a stubbed model, so
a green suite proves the code does what it says -- not that Supabase accepts
it or that DeepSeek answers. This script closes that gap. Run it from
``Backend/``::

    python -m scripts.verify_setup

It never writes a row and never sends a WhatsApp message. The one network
cost is a tiny prompt per configured LLM provider.

Exit code is 0 when nothing is broken, 1 when something is.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, List, Optional, Tuple

OK = "  OK   "
WARN = " WARN  "
FAIL = " FAIL  "

# Every table the backend touches. A missing one means schema.sql was never
# applied, or was applied to a different project than SUPABASE_URL points at.
REQUIRED_TABLES = (
    "zones",
    "people",
    "reports",
    "incidents",
    "cases",
    "events",
    "volunteers",
    "dispatches",
    "responder_links",
    "outbox",
    "registrations",
    "zone_alerts",
)

# Columns added after the first schema. Present means the migration ran.
RECENT_COLUMNS = (
    ("incidents", "location_source"),
    ("zones", "volunteer_group"),
    ("outbox", "suppressed_reason"),
)


class Report:
    def __init__(self) -> None:
        self.failures = 0
        self.warnings = 0

    def ok(self, label: str, detail: str = "") -> None:
        print(f"[{OK}] {label}{(' — ' + detail) if detail else ''}")

    def warn(self, label: str, detail: str = "") -> None:
        self.warnings += 1
        print(f"[{WARN}] {label}{(' — ' + detail) if detail else ''}")

    def fail(self, label: str, detail: str = "") -> None:
        self.failures += 1
        print(f"[{FAIL}] {label}{(' — ' + detail) if detail else ''}")


def section(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


# ─── Checks ────────────────────────────────────────────────────────────────


def check_config(report: Report) -> None:
    section("Configuration")
    from core import config

    problems = config.startup_report()
    if not problems:
        report.ok("startup_report has no complaints")
    for problem in problems:
        # A missing emergency number is a real gap, not a style note.
        if "EMERGENCY_" in problem or "DEMO_ALLOWLIST" in problem:
            report.fail("config", problem)
        else:
            report.warn("config", problem)

    if config.MOCK_MODE:
        report.ok("MOCK_MODE is on", "no real WhatsApp sends, no model calls from intake")
    else:
        report.warn("MOCK_MODE is OFF", "live sends are enabled")

    volunteers = config.DEMO_VOLUNTEERS or []
    if not volunteers:
        report.fail("DEMO_VOLUNTEERS is empty", "seeding will use placeholder phones")
    else:
        report.ok(f"DEMO_VOLUNTEERS has {len(volunteers)} entries")
        for index, entry in enumerate(volunteers):
            if not isinstance(entry, dict) or not entry.get("phone"):
                report.fail(f"DEMO_VOLUNTEERS[{index}]", "no phone field")


def check_supabase(report: Report) -> None:
    section("Supabase")
    from core.db import DbError, execute, get_db

    try:
        client = get_db()
        report.ok("client created")
    except DbError as exc:
        report.fail("cannot create client", str(exc))
        return

    for table in REQUIRED_TABLES:
        try:
            execute(client.table(table).select("*").limit(1))
            report.ok(f"table {table}")
        except Exception as exc:  # noqa: BLE001
            report.fail(f"table {table}", _short(exc))

    for table, column in RECENT_COLUMNS:
        try:
            execute(client.table(table).select(column).limit(1))
            report.ok(f"column {table}.{column}")
        except Exception as exc:  # noqa: BLE001
            report.fail(
                f"column {table}.{column}",
                "re-apply data/schema.sql — " + _short(exc),
            )

    try:
        result = execute(client.table("zones").select("id"))
        count = len(list(getattr(result, "data", None) or []))
        if count == 0:
            report.warn("zones table is empty", "run: python -m data.seed")
        else:
            report.ok(f"{count} zones seeded")
    except Exception as exc:  # noqa: BLE001
        report.fail("counting zones", _short(exc))


def check_llm(report: Report) -> None:
    section("LLM providers")
    from services import llm

    chain = llm.provider_chain()
    if not chain:
        report.fail("no provider configured", "set DEEPSEEK_API_KEY, GROQ_API_KEY or GEMINI_API_KEY")
        return

    report.ok("fallback order", " -> ".join(provider.name for provider in chain))

    for provider in chain:
        api_key, model = llm.credentials(provider.name)
        try:
            content = llm._chat(
                provider,
                api_key,
                model,
                'Reply with this exact JSON and nothing else: {"ok": true}',
                "Reply now.",
                15,
            )
            parsed = json.loads(content)
        except Exception as exc:  # noqa: BLE001
            report.fail(f"{provider.name} ({model})", _short(exc))
            # A model name goes stale on the provider's schedule, not ours, so
            # ask the key itself what it can reach instead of guessing again.
            if _looks_like_a_model_problem(exc):
                _suggest_models(report, provider, api_key)
            continue

        if isinstance(parsed, dict):
            report.ok(f"{provider.name} ({model})", "answered with valid JSON")
        else:
            report.fail(f"{provider.name} ({model})", "did not return a JSON object")


def check_extraction(report: Report) -> None:
    """The real test: does a live model fill the shape intake expects?"""
    section("Live extraction")
    from core import config
    from services import extract, llm

    if not llm.available():
        report.warn("skipped", "no provider configured")
        return

    was_mock = config.MOCK_MODE
    config.MOCK_MODE = False
    try:
        result = extract.extract_report(
            "Water is rising in our ground floor home in Gulistan e Jauhar. "
            "My elderly mother is alone with me."
        )
    except Exception as exc:  # noqa: BLE001
        report.fail("extract_report raised", _short(exc))
        return
    finally:
        config.MOCK_MODE = was_mock

    if result.get("category") == "flood":
        report.ok("category", "flood")
    else:
        report.warn("category", f"got {result.get('category')!r}, expected 'flood'")

    if result.get("zone_guess") == "johar":
        report.ok("area resolution", "'Gulistan e Jauhar' -> johar")
    else:
        report.fail(
            "area resolution",
            f"got {result.get('zone_guess')!r}, expected 'johar'",
        )

    vuln = result.get("vulnerability") or {}
    if vuln.get("elderly") is True:
        report.ok("vulnerability", "elderly detected")
    else:
        report.warn("vulnerability", f"elderly came back {vuln.get('elderly')!r}")

    # Only fields this probe says nothing about. "alone with me" DOES carry
    # information about being alone, so False there is the model reading the
    # sentence correctly rather than inventing an answer.
    never_mentioned = ("mobility_limited", "chronic_illness")
    invented = [key for key in never_mentioned if vuln.get(key) is not None]
    if invented:
        report.fail(
            "vulnerability guessing",
            f"model answered {', '.join(invented)} though the report never mentions them",
        )
    else:
        report.ok("unmentioned vulnerability stays null")

    _check_bare_report(report)


def _check_bare_report(report: Report) -> None:
    """A report carrying no vulnerability information must produce none.

    This is the check that matters. ``risk.vulnerability_score`` gives an
    unknown field half weight and a False field zero, so a model that guesses
    False makes a person look *safer* than one we simply never asked about.
    """
    from core import config
    from services import extract

    was_mock = config.MOCK_MODE
    config.MOCK_MODE = False
    try:
        bare = extract.extract_report("There is a fire in my kitchen in Korangi.")
    except Exception as exc:  # noqa: BLE001
        report.fail("bare-report probe raised", _short(exc))
        return
    finally:
        config.MOCK_MODE = was_mock

    vuln = bare.get("vulnerability") or {}
    answered = [key for key, value in vuln.items() if value is not None]
    if answered:
        report.fail(
            "vulnerability invented on a bare report",
            f"model answered {', '.join(answered)} from a sentence stating none of them",
        )
    else:
        report.ok("bare report invents no vulnerability")


def check_whatsapp(report: Report) -> None:
    section("WhatsApp")
    from core import config

    for name in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_ID", "WHATSAPP_VERIFY_TOKEN"):
        if getattr(config, name, ""):
            report.ok(name, "set")
        else:
            report.fail(name, "missing")

    if config.WHATSAPP_APP_SECRET:
        report.ok("WHATSAPP_APP_SECRET", "webhook signatures will be verified")
    else:
        report.warn("WHATSAPP_APP_SECRET", "inbound signatures are NOT verified")

    if config.WHATSAPP_PUBLIC_NUMBER:
        report.ok("WHATSAPP_PUBLIC_NUMBER", "join links can be built")
    else:
        report.warn("WHATSAPP_PUBLIC_NUMBER", "registration join links will be missing")

    print("\n  Note: nothing was sent. A real send is only proven by messaging")
    print("  the number from an allow-listed phone and watching the outbox table.")


def _looks_like_a_model_problem(exc: Exception) -> bool:
    text = str(exc).lower()
    return "model" in text and ("404" in text or "not found" in text or "no longer available" in text)


def _suggest_models(report: Report, provider: Any, api_key: str, limit: int = 8) -> None:
    """Print the model ids this key can actually reach.

    Every provider here speaks the OpenAI API, which includes listing models,
    so this works the same way for all of them.
    """
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=provider.base_url)
        names = sorted(model.id for model in client.models.list())
    except Exception as exc:  # noqa: BLE001
        report.warn(f"{provider.name}: could not list models", _short(exc))
        return

    if not names:
        report.warn(f"{provider.name}: the key reaches no models")
        return

    env_var = f"{provider.name.upper()}_MODEL"
    preferred = [name for name in names if "flash" in name or "mini" in name] or names
    print(f"         available models ({len(names)}): {', '.join(names[:limit])}")
    print(f"         fix: set {env_var}={preferred[0]} in .env")


def _short(exc: Exception, limit: int = 160) -> str:
    text = " ".join(str(exc).split())
    return text[:limit] + ("..." if len(text) > limit else "")


def main() -> int:
    report = Report()
    checks: List[Tuple[str, Callable[[Report], None]]] = [
        ("config", check_config),
        ("supabase", check_supabase),
        ("llm", check_llm),
        ("extraction", check_extraction),
        ("whatsapp", check_whatsapp),
    ]

    for name, check in checks:
        try:
            check(report)
        except Exception as exc:  # noqa: BLE001 - one broken check must not hide the rest
            report.fail(f"{name} check crashed", _short(exc))

    print()
    if report.failures:
        print(f"{report.failures} failure(s), {report.warnings} warning(s).")
        return 1
    print(f"No failures. {report.warnings} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
