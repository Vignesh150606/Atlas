# ATLAS Contribution Guide

Thank you for your interest in contributing to PROJECT ATLAS. We welcome contributions from the community to help build the ultimate personal AI companion.

## How to Contribute

The contribution process follows a standard open-source workflow. Please ensure your changes align with the project's vision and architectural principles.

1.  **Fork the repository** and create your branch from `develop`.
2.  **Follow coding standards** as outlined in the [Coding Standards](./CodingStandards.md) document.
3.  **Write tests** for any new features or bug fixes.
4.  **Submit a Pull Request** with a clear description of the changes and the problem they solve.

## Branching Model

| Branch | Purpose |
| :--- | :--- |
| `main` | Production-ready code. |
| `develop` | Integration branch for features. |
| `feature/*` | New features or enhancements. |
| `bugfix/*` | Critical fixes. |

## Pull Request Guidelines

Before submitting a pull request, please verify the following:
- The code builds successfully on both backend and Android.
- All tests pass (`pytest` and `./gradlew test`).
- Documentation has been updated if necessary.
- The commit messages are clear and follow the conventional commits format.

> **Note:** We prioritize maintainability and modularity. If a proposed change introduces tight coupling or breaks the provider-independent design, it may be requested for revision.
