from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "ATLAS"
    VERSION: str = "1.0"
    API_V1_STR: str = "/api/v1"
    APP_ENV: str = "development"
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./atlas.db"
    
    # LLM Providers
    DEFAULT_LLM_PROVIDER: str = "mock"
    OPENAI_API_KEY: Optional[str] = None
    CLAUDE_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    CLAUDE_MODEL: str = "claude-sonnet-5"
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_MODEL: str = "gemini-2.0-flash"
    OLLAMA_MODEL: str = "llama3.1"

    # Conversation / context window
    MAX_HISTORY_MESSAGES: int = 20  # trimmed by ConversationService before each generation
    MAX_RETRIEVED_MEMORIES: int = 5

    # Phase 12 (ARCH-TZ): fallback IANA zone used whenever a request carries
    # no client_timezone (see app/utils/timezone.py::resolve_zone). Every
    # DateTime column stays naive-UTC in storage - this only controls how
    # "now"/"today" are *resolved and rendered* when the client doesn't say.
    # Defaulting to the developer's own zone rather than "UTC" matches how
    # this single-user app has always been used in practice; a real client
    # timezone (sent by the Android app - see ChatRequest.client_timezone)
    # always takes precedence over this fallback.
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"

    # Personal Knowledge System (Phase 6)
    MAX_DOCUMENT_SIZE_MB: int = 20
    MAX_RETRIEVED_DOCUMENTS: int = 5
    SUPPORTED_DOCUMENT_TYPES: tuple = ("pdf", "markdown", "txt", "json", "csv")
    MAX_ENTITY_RELATIONSHIP_PAIRS_PER_DOCUMENT: int = 200  # caps O(n^2) co-occurrence pairing on entity-dense documents

    # Weather provider (Phase 9 - see app/providers/weather.py). Defaults to
    # "unconfigured": WeatherSkill will honestly report that weather isn't
    # set up rather than fabricating data, until a real provider is
    # implemented and both of these are set.
    WEATHER_PROVIDER: str = "unconfigured"
    WEATHER_API_KEY: Optional[str] = None

    # Security
    SECRET_KEY: str = "secret-key-for-development-only"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    # Phase 11: a single shared API key, not a multi-user auth system (see
    # app/models/user.py's docstring - that's reserved for a real future
    # auth layer, deliberately not reused here). Checked via
    # app.core.deps.verify_api_key on every route except /health. When
    # unset (the default), auth is a no-op and the API stays exactly as
    # open as it was before Phase 11 - this is an opt-in hardening step
    # for a trusted-network deployment, not a breaking change to existing
    # setups. Sent by the Android app as the "X-API-Key" header (see
    # android/.../di/AppModule.kt's ApiKeyInterceptor).
    API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()
