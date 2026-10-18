"""Login, logout, and the dependency every protected route hangs off.

The session lives in an HttpOnly cookie rather than a bearer token in
JavaScript, for two reasons. JavaScript cannot read an HttpOnly cookie, so a
script injected into the page cannot steal the session. And ``EventSource``
-- which the control room uses for ``/events`` -- cannot set an Authorization
header at all, so a bearer token would have left the live stream either
unprotected or broken.

``SameSite=Lax`` keeps the cookie off cross-site requests, which is what
stops another site from POSTing an approval on a logged-in coordinator's
behalf. It is not a full CSRF defence and the README says so.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from core import auth, config

logger = logging.getLogger("safezone.routes.auth")

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str = Field(max_length=200)
    password: str = Field(max_length=400)


def require_admin(request: Request) -> str:
    """FastAPI dependency. Raises 401 unless the caller has a live session.

    Returns the signed-in email, so a route can record who acted.
    """
    email = auth.read_session(request.cookies.get(auth.SESSION_COOKIE))
    if email is None:
        raise HTTPException(status_code=401, detail="Sign in to view this.")
    return email


@router.post("/api/auth/login")
def login(body: LoginRequest, request: Request, response: Response) -> Dict[str, Any]:
    try:
        email = auth.authenticate(body.email, body.password)
    except auth.AuthError as exc:
        # Logged without the password and without the attempted address, so a
        # typo'd password never lands in a log file.
        logger.warning("Rejected a sign-in attempt: %s", exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    token, max_age = auth.issue_session(email)

    response.set_cookie(
        auth.SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        # Secure only over HTTPS: a Secure cookie is silently dropped on
        # http://localhost, which would make local development look broken.
        secure=request.url.scheme == "https",
        path="/",
    )

    logger.info("Signed in")
    return {"email": email, "expires_in": max_age}


@router.post("/api/auth/logout")
def logout(response: Response) -> Dict[str, Any]:
    """Clear the cookie.

    The token stays valid until it expires -- sessions are signed, not
    stored, so there is nothing to revoke. Rotating SESSION_SECRET is how you
    end every session at once.
    """
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return {"signed_out": True}


@router.get("/api/auth/me")
def me(request: Request) -> Dict[str, Any]:
    """Who is signed in, if anyone.

    Always 200. The page calls this on load to decide whether to show the
    control room or the login form, and a 401 here would be an error in the
    console on every first visit by a signed-out user.
    """
    email = auth.read_session(request.cookies.get(auth.SESSION_COOKIE))
    return {
        "authenticated": email is not None,
        "email": email,
        "configured": auth.is_configured(),
    }


# Re-exported so route modules import the guard from one place.
__all__ = ["router", "require_admin", "LoginRequest"]
