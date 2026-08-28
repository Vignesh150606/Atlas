"""Shared time helpers.

`datetime.utcnow()` is deprecated (Python 3.12+) in favor of the
timezone-aware `datetime.now(timezone.utc)`. But every DateTime column
in this codebase (see app/models/*.py, app/models/base.py) is a plain,
timezone-*naive* `DateTime` - not `DateTime(timezone=True)` - so
introducing a genuinely timezone-aware datetime anywhere it might later
be compared against a value read back from the database (or against
another naive value elsewhere in the same service) would raise
`TypeError: can't compare offset-naive and offset-aware datetimes` at
runtime. Making the whole storage layer timezone-aware, and deciding
how timestamps arrive from the Android client, is a legitimate future
improvement - but a larger, separate, coordinated change (a new Alembic
migration among other things), not something to fold into a
deprecation-warning cleanup. See docs/Phase10_BugFixes_Followup.md and
docs/Phase11_Report.md for that reasoning.

`utc_now()` takes the same non-deprecated code path as
`datetime.now(timezone.utc)` but strips the tzinfo before returning, so
the result is bit-for-bit interchangeable with what `datetime.utcnow()`
used to produce: a naive datetime whose value is the current moment in
UTC. Use this everywhere `datetime.utcnow()` was previously used -
including as a bare callable (e.g. SQLAlchemy `Column(..., default=
utc_now)`), matching how `datetime.utcnow` itself was used.
"""
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
