# PROJECT: ATLAS - Personal AI Companion (Phase 1 MVP)

ATLAS is a cross-platform personal AI assistant designed to be a long-term companion. It lives primarily on Android and communicates naturally through voice and text, leveraging a modular backend that supports multiple LLM providers and a flexible memory system.

---

## Phase 1 Implementation Status

- ✅ **Backend**: FastAPI 0.110.0, SQLAlchemy 2.0.28 async, SQLite database initialization.
- ✅ **Health Check Endpoint**: `/api/v1/health` returning `{"status":"healthy", "version":"1.0", "database":"connected"}`.
- ✅ **Provider Abstraction**: `LLMProvider` interface implemented with `MockProvider` echoing responses.
- ✅ **Database Models & Repositories**: Users, Conversations, Messages, Memory Items, Settings using generic repository pattern.
- ✅ **Android App**: Jetpack Compose UI, Material 3, Hilt DI, Retrofit networking, MVVM with `ChatViewModel`.
- ✅ **Android Navigation**: Splash -> Chat -> Settings & About screens.
- ✅ **Backend Communication**: End-to-end flow Android ➔ Retrofit ➔ FastAPI ➔ MockProvider ➔ Response rendering.
- ✅ **Automated Tests**: Pytest test suite (100% pass), Android repository & ViewModel unit tests.

---

## Core Architecture

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.x (aiosqlite), Pydantic v2.
- **Frontend**: Android (Kotlin 1.9, Jetpack Compose, Material 3, Hilt, Retrofit).
- **Design**: Modular, provider-independent, and scalable layer architecture.

---

## Quick Start

### 1. Backend Setup & Run

```bash
cd backend

# Option A: Python virtual environment
python -m venv venv
# On Windows: venv\Scripts\activate
# On Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Run FastAPI dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify backend health:
```bash
curl http://localhost:8000/api/v1/health
```
Response:
```json
{
  "status": "healthy",
  "version": "1.0",
  "database": "connected"
}
```

Run Pytest suite:
```bash
pytest
```

---

### 2. Android Setup & Run

1. Open the `android` directory in **Android Studio (Hedgehog or newer)**.
2. Ensure JDK 17 is selected under **Project Structure -> SDK Location**.
3. Sync Gradle and run the `:app` module on an Android Emulator or physical device (API 26+).

> **Note for Android Emulator:** The app connects to `http://10.0.2.2:8000/api/v1/` which maps directly to your host machine's `localhost:8000`.

---

## Architecture Diagram

```
+---------------------------------------+
|              Android App              |
| (Compose UI + MVVM + Hilt + Retrofit) |
+-------------------+-------------------+
                    | HTTP REST API
                    v
+---------------------------------------+
|            FastAPI Backend            |
|       (App Lifespan & Logging)        |
+-------------------+-------------------+
                    |
       +------------+------------+
       |                         |
       v                         v
+--------------+       +-------------------+
|  Repository  |       | Provider Factory  |
|  (SQLAlchemy)|       |  (MockProvider)   |
+-------+------+       +---------+---------+
        |                        |
        v                        v
+--------------+       +-------------------+
|  SQLite DB   |       |  Echo Response    |
| (atlas.db)   |       |  "ATLAS received" |
+--------------+       +-------------------+
```

---

## Known Limitations (Phase 1 MVP)

- External LLM provider APIs (Claude, OpenAI) are mocked using `MockProvider` (as required for Phase 1).
- Advanced memory RAG, vector embeddings, and speech recognition/TTS are scheduled for Phase 2+.

---

## Documentation

- [Architecture](./docs/Architecture.md)
- [Folder Structure](./docs/FolderStructure.md)
- [Development Guide](./docs/DevelopmentGuide.md)
- [API Reference](./docs/API.md)
- [Roadmap](./docs/Roadmap.md)
- [Coding Standards](./docs/CodingStandards.md)
- [Contribution Guide](./docs/ContributionGuide.md)
