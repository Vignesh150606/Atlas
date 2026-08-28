"""Phase 12 / SECURITY_PLAN.md S2: Settings.validate_for_environment().

Follows the same settings-mutation pattern as tests/test_api_key_auth.py -
settings is a process-wide singleton (app.core.config.settings), so every
test that mutates it must restore the original value afterward or it leaks
into unrelated later tests.
"""
import pytest
from app.core.config import settings


@pytest.fixture
def restore_settings():
    original = (settings.APP_ENV, settings.API_KEY, settings.SECRET_KEY)
    yield
    settings.APP_ENV, settings.API_KEY, settings.SECRET_KEY = original


def test_development_env_never_raises(restore_settings):
    settings.APP_ENV = "development"
    settings.API_KEY = None
    settings.SECRET_KEY = "secret-key-for-development-only"
    settings.validate_for_environment()  # must not raise


def test_production_env_without_api_key_raises(restore_settings):
    settings.APP_ENV = "production"
    settings.API_KEY = None
    settings.SECRET_KEY = "a-real-secret"
    with pytest.raises(RuntimeError, match="API_KEY"):
        settings.validate_for_environment()


def test_production_env_with_default_secret_key_raises(restore_settings):
    settings.APP_ENV = "production"
    settings.API_KEY = "real-key"
    settings.SECRET_KEY = "secret-key-for-development-only"
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        settings.validate_for_environment()


def test_production_env_fully_configured_does_not_raise(restore_settings):
    settings.APP_ENV = "production"
    settings.API_KEY = "real-key"
    settings.SECRET_KEY = "a-real-secret"
    settings.validate_for_environment()  # must not raise


def test_production_env_reports_both_problems_at_once(restore_settings):
    settings.APP_ENV = "production"
    settings.API_KEY = None
    settings.SECRET_KEY = "secret-key-for-development-only"
    with pytest.raises(RuntimeError) as excinfo:
        settings.validate_for_environment()
    assert "API_KEY" in str(excinfo.value)
    assert "SECRET_KEY" in str(excinfo.value)


def test_cors_origins_default_is_empty():
    # Empty by default: the only client is the native Android app, which
    # CORS does not apply to - see app/main.py's comment on this setting.
    assert settings.CORS_ORIGINS == []
