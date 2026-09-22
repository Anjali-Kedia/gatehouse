"""Per-visitor sandbox session identity, plus CSRF protection for the writes
that identity guards.

Every visitor gets an opaque, httpOnly session cookie on first contact. All
evaluations, approvals, and executions are scoped to it, and `evaluations.py`
checks it on every approve/execute call — an evaluation ID alone is never
sufficient to act on someone else's sandbox.

`SameSite=Lax` already blocks the session cookie from being attached to
cross-site subresource requests and cross-site POST navigations, which covers
most of the practical CSRF surface here. A double-submit CSRF token is added
anyway rather than relying on that alone: it doesn't depend on every browser
implementing SameSite correctly, and it stays correct even if a future
endpoint ever accepts a mutating GET.
"""
import secrets
import uuid

from fastapi import Depends, HTTPException, Request, Response

from gatehouse.config import settings

_SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # a week is plenty for a demo session
CSRF_COOKIE_NAME = "gatehouse_csrf"
CSRF_HEADER_NAME = "x-csrf-token"


def get_sandbox_session_id(request: Request, response: Response) -> str:
    session_id = request.cookies.get(settings.session_cookie_name)
    is_new_session = session_id is None
    if is_new_session:
        session_id = uuid.uuid4().hex
        response.set_cookie(
            settings.session_cookie_name,
            session_id,
            httponly=True,
            samesite="lax",
            max_age=_SESSION_MAX_AGE_SECONDS,
        )
    is_new_csrf_cookie = not request.cookies.get(CSRF_COOKIE_NAME)
    if is_new_csrf_cookie:
        # Not httpOnly — the frontend must be able to read it and echo it back
        # as a header. That's the entire double-submit mechanism: an attacker
        # on another origin can trigger a cross-site request, but can't read
        # this cookie to put its value in the header.
        response.set_cookie(
            CSRF_COOKIE_NAME,
            secrets.token_urlsafe(32),
            httponly=False,
            samesite="lax",
            max_age=_SESSION_MAX_AGE_SECONDS,
        )
    # Nothing to forge against yet, so skip the check on the request that
    # establishes either cookie — including an old session hitting this code
    # for the first time. (Must be decided here: raising in verify_csrf would
    # discard the set_cookie calls above.)
    request.state.skip_csrf_check = is_new_session or is_new_csrf_cookie
    return session_id


def verify_csrf(request: Request, sandbox_session_id: str = Depends(get_sandbox_session_id)) -> None:
    if getattr(request.state, "skip_csrf_check", False):
        return
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="Missing or invalid CSRF token.")
