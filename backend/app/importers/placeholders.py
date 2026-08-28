from abc import ABC, abstractmethod
from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import Document


class ExternalSourceImporter(ABC):
    """Base shape for importers that pull from an external system rather
    than a single uploaded file. None of these are implemented in Phase 6 -
    each would need real integration work (OAuth flow, API client, sync
    scheduling) that's out of scope here. They're registered now so the
    source type exists end-to-end (DB enum, planner/tool routing can
    reference it) without pretending the integration is built.

    This mirrors how ClaudeProvider/GeminiProvider/OllamaProvider existed
    as real classes before their API keys were configured, and how
    User/Setting were kept as intentionally-reserved scaffolding rather
    than deleted - "not built yet" is tracked explicitly, not left
    ambiguous.
    """

    source_name: str = "external"

    def __init__(self, db: AsyncSession):
        self.db = db

    @abstractmethod
    async def sync(self, **kwargs: Any) -> List[Document]:
        """Pull content from the external source and import it as
        Documents. Not implemented in Phase 6."""
        raise NotImplementedError(
            f"{self.source_name} sync is a future-ready placeholder, not implemented in Phase 6."
        )


class CalendarImporter(ExternalSourceImporter):
    """Future: sync events from a calendar (Google Calendar / CalDAV) as
    Documents, so upcoming events feed the same knowledge/timeline system
    as imported files. Needs OAuth + a calendar API client."""

    source_name = "calendar"

    async def sync(self, **kwargs: Any) -> List[Document]:
        raise NotImplementedError("Calendar sync requires OAuth + a calendar API client - not built yet.")


class GitHubImporter(ExternalSourceImporter):
    """Future: sync repo READMEs / issues / PR descriptions as Documents.
    Needs a GitHub API token and a repo allowlist."""

    source_name = "github"

    async def sync(self, **kwargs: Any) -> List[Document]:
        raise NotImplementedError("GitHub sync requires an API token + repo config - not built yet.")


class NotesImporter(ExternalSourceImporter):
    """Future: sync from an external notes app (e.g. Apple Notes, Google
    Keep, Notion). Needs a source-specific export/API integration."""

    source_name = "notes"

    async def sync(self, **kwargs: Any) -> List[Document]:
        raise NotImplementedError("Notes sync needs a source-specific integration - not built yet.")


class ResumeImporter(ExternalSourceImporter):
    """Future: a specialized importer that, unlike the generic PDF/DOCX
    pipeline, is tuned to pull structured PERSON/SKILL/COMPANY/COURSE
    entities specifically out of resume-shaped documents (sections like
    Experience/Education/Skills) rather than relying on the generic
    EntityExtractor rules. Not built in Phase 6 - today a resume PDF just
    goes through the normal PDF import pipeline like any other document.
    """

    source_name = "resume"

    async def sync(self, **kwargs: Any) -> List[Document]:
        raise NotImplementedError("Resume-specific structured extraction is not built yet.")


def get_placeholder_importer(source_name: str, db: AsyncSession) -> ExternalSourceImporter:
    registry: Dict[str, type] = {
        "calendar": CalendarImporter,
        "github": GitHubImporter,
        "notes": NotesImporter,
        "resume": ResumeImporter,
    }
    importer_cls = registry.get(source_name)
    if importer_cls is None:
        raise ValueError(f"Unknown external source '{source_name}'. Known: {', '.join(registry)}")
    return importer_cls(db)
