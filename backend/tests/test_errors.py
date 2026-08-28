"""Phase 12 / SECURITY_PLAN.md S10: app/core/errors.py::internal_error."""
from app.core.errors import internal_error


def test_internal_error_detail_does_not_leak_exception_text():
    secret_looking_detail = "duplicate key value violates unique constraint 'memories_pkey' at /srv/atlas/db.py:42"
    exc = ValueError(secret_looking_detail)
    http_exc = internal_error(exc, context="test")
    assert http_exc.status_code == 500
    assert secret_looking_detail not in http_exc.detail
    assert "internal error" in http_exc.detail.lower()


def test_internal_error_includes_a_correlation_id():
    http_exc = internal_error(ValueError("boom"), context="test")
    assert "Reference:" in http_exc.detail
