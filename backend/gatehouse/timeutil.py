from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive-but-UTC "now". SQLite drops tzinfo on round-trip, so every stored
    datetime in this schema is UTC by convention rather than by tzinfo — always use
    this helper (never bare datetime.now()/utcnow()) so comparisons against values
    read back from the database — e.g. approval expiry — stay apples-to-apples.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_utc(dt: datetime) -> datetime:
    """Tag a naive-but-UTC value (see `utcnow`) as tz-aware UTC before it leaves
    the process — e.g. over the API as JSON. Pydantic serializes a naive datetime
    with no offset at all, which a browser's `Date` parser then reads as *local*
    time; in any timezone ahead of UTC that silently shifts the value into the
    past, which is exactly how "approval expires_at" ends up reading as already
    expired the instant it's created. Never send a naive datetime over the wire.
    """
    return dt.replace(tzinfo=timezone.utc)
