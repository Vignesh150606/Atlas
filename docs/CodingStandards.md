# ATLAS Coding Standards

To maintain a high-quality and consistent codebase, all contributors must follow these standards. These rules ensure that the project remains maintainable and scalable as it evolves.

## Python (Backend)

We follow PEP 8 with some additional requirements for modern Python development.

- **Type Hinting**: All function signatures must include type hints for parameters and return values.
- **Asynchronous Code**: Use `async/await` for all I/O bound operations, including database queries and external API calls.
- **Docstrings**: Use Google-style docstrings for all public modules, classes, and functions.
- **Pydantic**: Use Pydantic models for request validation and response serialization.

## Kotlin (Android)

The Android codebase follows official Google and Kotlin style guides.

- **Compose**: Use declarative UI with Jetpack Compose. Avoid XML layouts unless strictly necessary for third-party integrations.
- **MVVM**: Strictly separate UI (Compose), logic (ViewModel), and data (Repository).
- **Coroutines**: Use Kotlin Coroutines and Flow for asynchronous programming and reactive data streams.
- **Dependency Injection**: Use Hilt for all DI requirements.

## General Principles

| Principle | Description |
| :--- | :--- |
| **DRY** | Don't Repeat Yourself. Extract common logic into utilities or base classes. |
| **SOLID** | Follow SOLID principles to ensure modular and testable code. |
| **Clean Code** | Write code that is easy to read and understand. Favor clarity over cleverness. |
| **Documentation** | Document "why" something is done, not just "what" is being done. |

## Formatting Tools

Please ensure your editor is configured to use the following tools:
- **Backend**: `black`, `isort`, `mypy`.
- **Frontend**: `ktlint`.
