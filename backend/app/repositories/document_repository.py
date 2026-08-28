from typing import Optional, List, Dict, Any
from datetime import datetime
from app.utils.time import utc_now
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models.document import Document


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, db: AsyncSession):
        super().__init__(Document, db)

    async def get_by_id(self, document_id: str, include_deleted: bool = False) -> Optional[Document]:
        query = select(Document).filter(Document.id == document_id)
        if not include_deleted:
            query = query.filter(Document.deleted_at.is_(None))
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_hash(self, content_hash: str) -> Optional[Document]:
        """Used for import-time de-duplication: re-importing byte-identical
        content returns the existing document instead of creating a copy."""
        result = await self.db.execute(
            select(Document).filter(Document.content_hash == content_hash, Document.deleted_at.is_(None))
        )
        return result.scalars().first()

    async def get_filtered(
        self,
        file_type: Optional[str] = None,
        source: Optional[str] = None,
        tag: Optional[str] = None,
        include_deleted: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Document]:
        query = select(Document)
        if not include_deleted:
            query = query.filter(Document.deleted_at.is_(None))
        if file_type:
            query = query.filter(Document.file_type == file_type)
        if source:
            query = query.filter(Document.source == source)

        query = query.order_by(Document.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        documents = result.scalars().all()

        if tag:
            documents = [d for d in documents if isinstance(d.tags, list) and tag in d.tags]
        return documents

    async def search(self, query_str: str, file_type: Optional[str] = None, limit: int = 50) -> List[Document]:
        """Keyword search over title/content/tags. No FTS5 virtual table for
        documents (unlike memories) - document content can be large, and a
        straightforward LIKE search across title/content is sufficient for
        Phase 6's "no vector DB, use metadata + keyword search" scope."""
        query_str_clean = query_str.strip()
        if not query_str_clean:
            return await self.get_filtered(file_type=file_type, limit=limit)

        like_pattern = f"%{query_str_clean}%"
        query = select(Document).filter(
            Document.deleted_at.is_(None),
            (Document.title.ilike(like_pattern) | Document.content.ilike(like_pattern)),
        )
        if file_type:
            query = query.filter(Document.file_type == file_type)
        query = query.order_by(Document.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_document(self, obj_in: Dict[str, Any]) -> Document:
        return await self.create(obj_in)

    async def soft_delete(self, document_id: str) -> Optional[Document]:
        document = await self.get_by_id(document_id, include_deleted=False)
        if document:
            document.deleted_at = utc_now()
            self.db.add(document)
            await self.db.flush()
        return document
