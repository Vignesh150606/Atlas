# ATLAS Development Guide

This guide provides the necessary information for developers to set up, build, and contribute to the ATLAS project. The architecture is designed to be modular, ensuring that components can be developed and tested in isolation.

## Environment Setup

The project requires Python 3.12+ for the backend and Android Studio Hedgehog or newer for the frontend. It is recommended to use a virtual environment for Python dependencies to maintain a clean workspace.

| Component | Requirement | Recommended Tool |
| :--- | :--- | :--- |
| Backend | Python 3.12+ | PyCharm / VS Code |
| Frontend | Kotlin 1.9+ | Android Studio |
| Database | SQLite / PostgreSQL | DBeaver / TablePlus |
| Container | Docker & Compose | Docker Desktop |

## Backend Development

To start the backend development server, navigate to the `backend` directory and install the dependencies. The application uses FastAPI, which provides an interactive Swagger UI for testing endpoints.

> **Note:** Ensure you have created a `.env` file based on the provided configuration settings before starting the server.

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Android Development

The Android application is built using Jetpack Compose and follows the MVVM pattern. Dependency injection is handled by Hilt, and networking is managed through Retrofit.

1. Open the `android` folder in Android Studio.
2. Sync the project with Gradle files.
3. Run the application on an emulator or physical device (API level 26+).

## Testing Strategy

Quality assurance is a priority for ATLAS. The backend uses `pytest` for unit and integration tests, while the Android app utilizes `JUnit` and `Compose Test`.

- **Backend Tests**: Run `pytest` in the `backend` directory.
- **Android Tests**: Run `./gradlew test` in the `android` directory.
