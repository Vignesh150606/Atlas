from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.parsers.registry import get_parser, infer_file_type, supported_file_types
from app.parsers.base import ParserError
from app.importers.base import DocumentImportError
from app.core.config import settings


class DocumentImporter:
    """Turns raw uploaded bytes into a persisted Document row.

    Scope: picks the right DocumentParser for the file's type, computes a
    content hash for de-duplication, and persists via DocumentRepository.
    Deliberately does NOT run entity extraction - that's DocumentService's
    job (see app/services/document_service.py), so this class stays a
    single-purpose import pipeline that's easy to reuse (e.g. from a batch
    import script) without dragging extraction along.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = DocumentRepository(db)

    async def import_file(
        self,
        filename: str,
        raw_bytes: bytes,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
        author: Optional[str] = None,
        source: str = "upload",
        file_type: Optional[str] = None,
    ) -> Tuple[Document, bool]:
        """Returns (document, was_created). was_created is False when the
        content hash matched an existing document - callers (DocumentService)
        use this to avoid re-running entity extraction on a re-upload of the
        same file."""
        resolved_type = file_type or infer_file_type(filename)
        if resolved_type is None:
            raise DocumentImportError(
                f"Unsupported file type for '{filename}'. Supported types: {', '.join(supported_file_types())}"
            )

        size_mb = len(raw_bytes) / (1024 * 1024)
        if size_mb > settings.MAX_DOCUMENT_SIZE_MB:
            raise DocumentImportError(
                f"File is {size_mb:.1f}MB, which exceeds the {settings.MAX_DOCUMENT_SIZE_MB}MB import limit."
            )

        content_hash = Document.compute_hash(raw_bytes)
        existing = await self.repository.get_by_hash(content_hash)
        if existing is not None:
            # Byte-identical content already imported - return the existing
            # row rather than creating a duplicate.
            return existing, False

        parser = get_parser(resolved_type)
        if parser is None:
            raise DocumentImportError(f"No parser registered for file type '{resolved_type}'.")

        try:
            parsed = parser.parse(raw_bytes, filename=filename)
        except ParserError:
            raise
        except Exception as e:  # noqa: BLE001 - convert any unexpected parser failure into a clean import error
            raise DocumentImportError(f"Failed to parse '{filename}': {e}")

        document = await self.repository.create_document({
            "title": title or filename,
            "source": source,
            "file_type": resolved_type,
            "original_filename": filename,
            "author": author,
            "tags": tags or [],
            "content": parsed.text,
            "structured_data": parsed.structured_data,
            "content_hash": content_hash,
            "size_bytes": len(raw_bytes),
        })
        return document, True
