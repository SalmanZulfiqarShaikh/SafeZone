"""The control-room login.

These are the tests that decide whether a stranger with the ngrok URL can
read every case, every reporter's name and number, and every volunteer's
position. A frontend route guard does not come into it: the question here is
only what the API answers.

The important ones are the negatives -- what a signed-out caller gets, what a
tampered cookie gets, and whether a failed login says which half was wrong.
"""

import pytest
from fastapi.testclient import TestClient

from core import auth, config

PASSWORD = "correct-horse-battery-staple"
EMAIL = "coordinator@example.com"

# Endpoints that must never answer a stranger. Each one is listed with why,
# so a future reader does not quietly drop one from the list.
PROTECTED = [
    ("get", "/api/cases"),              # reporter names, numbers, locations
    ("get", "/api/cases/1"),            # the same, in detail
    ("get", "/api/cases/1/dispatches"), # which volunteer went where
    ("get", "/api/volunteers"),         # who is on duty and where they are
    ("get", "/api/admin/status"),       # operational switches
    ("get", "/events"),                 # the live stream of all of the above
    ("post", "/api/proposals/1/approve"),
    ("post", "/api/cases/1/reopen"),
    ("post", "/api/cases/1/responderlink"),
    ("post", "/api/admin/killswitch"),
]

# Endpoints that must keep working without a login, and the reason.
PUBLIC = [
    ("get", "/api/hello"),       # health check
    ("get", "/api/zones"),       # the public registration dropdown needs it
    ("get", "/api/auth/me"),     # the page asks "am I signed in?" before login
]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "MOCK_MODE", True)
    monkeypatch.setattr(config, "ADMIN_EMAIL", EMAIL)
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", auth.hash_password(PASSWORD))
    monkeypatch.setattr(config, "SESSION_SECRET", "test-secret-not-a-real-one")
    monkeypatch.setattr(config, "SESSION_TTL_HOURS", 12)

    import main
    from routes import zones

    # Replace the NAME `zones.store` points at, not an attribute on the
    # shared store module -- `from routes import store` hands every route the
    # same object, so setting .select on it would feed zone rows to
    # /api/cases as well.
    class ZoneStore:
        @staticmethod
        def select(table, **filters):
            return [
                {"id": "johar", "name": "Gulistan-e-Jauhar", "lat": 24.92,
                 "lng": 67.13, "volunteer_group": "a", "risk_level": "elevated"},
            ]

    monkeypatch.setattr(zones, "store", ZoneStore)

    # raise_server_exceptions=False so a handler that fails for its own
    # reasons -- no database configured here -- comes back as a 500 response
    # instead of exploding out of the client. These tests care only about
    # whether the guard answered, and 500 is not 401.
    return TestClient(main.app, raise_server_exceptions=False)


def sign_in(client) -> None:
    response = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200


# ─── What a stranger can reach ─────────────────────────────────────────────


@pytest.mark.parametrize("method,path", PROTECTED)
def test_signed_out_is_refused(client, method, path):
    # client.request, not client.get: httpx's get() takes no json argument.
    response = client.request(method.upper(), path, json={} if method == "post" else None)
    assert response.status_code == 401, f"{path} answered a stranger"


@pytest.mark.parametrize("method,path", PUBLIC)
def test_public_endpoints_stay_public(client, method, path):
    response = client.request(method.upper(), path)
    assert response.status_code == 200, f"{path} needs a login but should not"


def test_the_webhook_is_not_behind_the_login(client):
    """Meta signs its calls and will never hold a session cookie.

    A 401 here would silently stop every inbound WhatsApp message, which is
    the whole product. Any status but 401 means the guard is off it.
    """
    response = client.post("/webhook/whatsapp", json={"object": "whatsapp_business_account"})
    assert response.status_code != 401


def test_a_responder_link_needs_no_login(client):
    """Fire and ambulance desks get a link, never an account."""
    assert client.get("/api/r/some-token").status_code != 401


# ─── Logging in ────────────────────────────────────────────────────────────


def test_correct_credentials_are_accepted(client):
    response = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200
    assert response.json()["email"] == EMAIL


def test_the_session_cookie_is_httponly(client):
    """JavaScript must not be able to read it, so an injected script cannot
    walk off with a live session."""
    response = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_a_wrong_password_is_refused(client):
    assert client.post(
        "/api/auth/login", json={"email": EMAIL, "password": "wrong"}
    ).status_code == 401


def test_a_wrong_email_is_refused(client):
    assert client.post(
        "/api/auth/login", json={"email": "someone@else.com", "password": PASSWORD}
    ).status_code == 401


def test_the_two_failures_are_indistinguishable(client):
    """A message that says "no such user" tells an attacker which half to
    keep trying. Both answers must read the same."""
    wrong_password = client.post(
        "/api/auth/login", json={"email": EMAIL, "password": "wrong"}
    )
    wrong_email = client.post(
        "/api/auth/login", json={"email": "someone@else.com", "password": PASSWORD}
    )
    assert wrong_password.json()["detail"] == wrong_email.json()["detail"]


def test_login_is_refused_when_the_server_has_no_credentials(client, monkeypatch):
    """Unconfigured must mean closed, never open."""
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", "")
    assert client.post(
        "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
    ).status_code == 401


# ─── Sessions ──────────────────────────────────────────────────────────────


def test_a_signed_in_caller_gets_past_the_guard(client):
    """Past the guard, not necessarily to a 200: these handlers want a
    database. Anything other than 401 means the session was accepted."""
    sign_in(client)
    assert client.get("/api/cases").status_code != 401


def test_me_reports_the_signed_in_user(client):
    sign_in(client)
    body = client.get("/api/auth/me").json()
    assert body["authenticated"] is True
    assert body["email"] == EMAIL


def test_me_is_honest_when_signed_out(client):
    body = client.get("/api/auth/me").json()
    assert body["authenticated"] is False
    assert body["email"] is None


def test_logout_clears_the_cookie(client):
    sign_in(client)
    client.post("/api/auth/logout")
    assert client.get("/api/cases").status_code == 401


def test_a_tampered_cookie_is_refused(client):
    client.cookies.set(auth.SESSION_COOKIE, f"{EMAIL}|99999999999|notarealsignature")
    assert client.get("/api/cases").status_code == 401


def test_a_forged_email_is_refused(client):
    """Swapping the email in a validly signed token must break the signature."""
    token, _ = auth.issue_session(EMAIL)
    _email, expires, signature = token.rsplit("|", 2)
    client.cookies.set(auth.SESSION_COOKIE, f"attacker@example.com|{expires}|{signature}")
    assert client.get("/api/cases").status_code == 401


def test_an_expired_session_is_refused(client, monkeypatch):
    """Issue a real session, then move the clock past its expiry.

    Minting one with a negative TTL would not work: issue_session clamps to a
    minimum of one hour so a misconfigured SESSION_TTL_HOURS cannot create
    sessions that are dead on arrival. Moving time forward exercises the
    expiry branch through the same path a real session takes.
    """
    sign_in(client)
    assert client.get("/api/cases").status_code != 401

    import time as real_time

    later = real_time.time() + (config.SESSION_TTL_HOURS + 1) * 3600
    monkeypatch.setattr(auth.time, "time", lambda: later)

    assert client.get("/api/cases").status_code == 401


def test_rotating_the_secret_ends_every_session(client, monkeypatch):
    """Sessions are signed rather than stored, so this is how they are
    revoked before they expire. The README says so; this proves it."""
    sign_in(client)
    monkeypatch.setattr(config, "SESSION_SECRET", "a-different-secret")
    assert client.get("/api/cases").status_code == 401


def test_changing_the_admin_email_ends_the_old_session(client, monkeypatch):
    sign_in(client)
    monkeypatch.setattr(config, "ADMIN_EMAIL", "someone@else.com")
    assert client.get("/api/cases").status_code == 401


# ─── Password hashing ──────────────────────────────────────────────────────


def test_a_hash_does_not_contain_the_password(client):
    assert PASSWORD not in auth.hash_password(PASSWORD)


def test_two_hashes_of_one_password_differ(client):
    """Salted, so a stolen hash cannot be matched against another account's."""
    assert auth.hash_password(PASSWORD) != auth.hash_password(PASSWORD)


def test_verify_accepts_the_right_password(client):
    assert auth.verify_password(PASSWORD, auth.hash_password(PASSWORD))


def test_verify_rejects_the_wrong_one(client):
    assert not auth.verify_password("nearly-right", auth.hash_password(PASSWORD))


@pytest.mark.parametrize("stored", ["", "garbage", "pbkdf2_sha256$notanumber$a$b", "md5$1$a$b"])
def test_a_malformed_hash_fails_closed(client, stored):
    assert not auth.verify_password(PASSWORD, stored)


def test_is_configured_needs_all_three(client, monkeypatch):
    assert auth.is_configured()
    for field in ("ADMIN_EMAIL", "ADMIN_PASSWORD_HASH", "SESSION_SECRET"):
        monkeypatch.setattr(config, field, "")
        assert not auth.is_configured()
        monkeypatch.undo()
        monkeypatch.setattr(config, "MOCK_MODE", True)
        monkeypatch.setattr(config, "ADMIN_EMAIL", EMAIL)
        monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", auth.hash_password(PASSWORD))
        monkeypatch.setattr(config, "SESSION_SECRET", "test-secret-not-a-real-one")
