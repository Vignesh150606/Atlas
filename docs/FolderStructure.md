# ATLAS Folder Structure

```text
atlas/
├── .github/             # CI/CD workflows
├── android/             # Android Kotlin project
│   ├── app/             # Main application module
│   │   ├── src/
│   │   │   ├── main/
│   │   │   │   ├── java/com/atlas/
│   │   │   │   │   ├── api/          # Networking
│   │   │   │   │   ├── data/         # Repositories & Models
│   │   │   │   │   ├── di/           # Dependency Injection
│   │   │   │   │   └── ui/           # Compose UI & ViewModels
│   │   │   │   └── AndroidManifest.xml
│   │   └── build.gradle.kts
│   └── build.gradle.kts
├── backend/             # Python FastAPI backend
│   ├── app/
│   │   ├── api/         # API Endpoints (v1)
│   │   ├── core/        # Config, logging, security
│   │   ├── database/    # SQLAlchemy setup
│   │   ├── models/      # DB Models
│   │   ├── providers/   # LLM Abstractions
│   │   ├── repositories/# Data access layer
│   │   ├── services/    # Business logic
│   │   ├── skills/      # Plugin system
│   │   └── main.py      # Entry point
│   ├── tests/           # Pytest suite
│   └── requirements.txt
├── docker/              # Docker & Compose files
├── docs/                # Project documentation
├── scripts/             # Utility & Setup scripts
└── shared/              # Shared assets/schemas
```
