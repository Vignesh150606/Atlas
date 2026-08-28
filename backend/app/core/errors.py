"""Phase 12 / SECURITY_PLAN.md S10: generic error responses for
unexpected/internal failures.

Several endpoints previously did `except Exception as e: raise
HTTPException(500, detail=str(e))` - the real exception text (which can
carry SQL fragments, file paths, or a provider's own error message) went
straight to the client. `RequestTrace` (app/observability/trace.py)
already has the right redaction property for chat-turn logging; this is
the same idea for the small number of non-chat endpoints that still
catch a bare Exception and need somewhere honest to put the detail
without handing it to whoever sent the request.

Not used for HTTPException re-raises or specific, expected exception
types (e.g. DocumentImportError/ParserError in documents.py, or a
ValueError meant as user-facing validation feedback) - those are
deliberate, already-safe messages, not a leak.
"""
import logging
import uuid
from fastapi import HTTPException, status

logger = logging.getLogger("atlas.errors")


def internal_error(exc: Exception, *, context: str) -> HTTPException:
    """Logs the real exception server-side with a correlation id, and
    returns an HTTPException whose client-visible detail is generic. Call
    this from an `except Exception as e:` block instead of building the
    HTTPException directly with `detail=str(e)`.
    """
    correlation_id = uuid.uuid4().hex[:12]
    logger.error("Unhandled error in %s [%s]: %s", context, correlation_id, exc, exc_info=True)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"An internal error occurred. Reference: {correlation_id}",
    )
