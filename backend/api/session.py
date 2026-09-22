"""Per-visitor sandbox session identity.

Every visitor gets an opaque, httpOnly session cookie on first contact. All
evaluations, approvals, and executions are scoped to it, and `evaluations.py`
checks it on every approve/execute call — an evaluation ID alone is never
sufficient to act on someone else's sandbox.
"""
import uuid

from fastapi import Request, Response

from gatehouse.config import settings

_SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # a week is plenty for a demo session


def get_sandbox_session_id(request: Request, response: Response) -> str:
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        return session_id
    session_id = uuid.uuid4().hex
    response.set_cookie(
        settings.session_cookie_name,
        session_id,
        httponly=True,
        samesite="lax",
        max_age=_SESSION_MAX_AGE_SECONDS,
    )
    return session_id
