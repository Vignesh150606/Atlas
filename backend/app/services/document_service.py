import itertools
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import Document
from app.models.entity import Entity
from app.repositories.document_repository import DocumentRepository
from app.repositories.entity_repository import EntityRepository
from app.importers.document_importer import DocumentImporter
from app.extraction.entity_extractor import EntityExtractor
from app.schemas.document import DocumentUpdate, DocumentFilterParams
from app.core.config import settings


class DocumentService:
    """Orchestrates the full document pipeline: import -> entity extraction
    -> relationship building, plus document CRUD/search. This is the layer
    ChatService/tools call into - DocumentImporter and EntityExtractor stay
    single-purpose and don't know about each other.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.importer = DocumentImporter(db)
        self.document_repository = DocumentRepository(db)
        self.entity_repository = EntityRepository(db)

    async def import_document(
        self,
        filename: str,
        raw_bytes: bytes,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
        author: Optional[str] = None,
        source: str = "upload",
    ) -> Document:
        document, was_created = await self.importer.import_file(
            filename, raw_bytes, title=title, tags=tags, author=author, source=source
        )
        if was_created:
            await self._extract_and_link_entities(document)
        return document

    async def _extract_and_link_entities(self, document: Document) -> List[Entity]:
        extracted = EntityExtractor.extract(document.content, document.structured_data)

        entities: List[Entity] = []
        for item in extracted:
            entity = await self.entity_repository.create_entity({
                "entity_type": item.entity_type.value,
                "name": item.name,
                "details": item.details,
                "document_id": document.id,
                "confidence": item.confidence,
            })
            entities.append(entity)

        # Relate every pair of entities extracted from this document as
        # "probably connected" - deliberately capped so an entity-dense
        # document (e.g. a big CSV) can't blow up into tens of thousands of
        # relationship rows.
        pairs = list(itertools.combinations(entities, 2))[: settings.MAX_ENTITY_RELATIONSHIP_PAIRS_PER_DOCUMENT]
        for entity_a, entity_b in pairs:
            await self.entity_repository.create_relationship(entity_a.id, entity_b.id)

        # Phase 9 / cross-document reasoning: also link each newly-extracted
        # entity to any exact-match (same name+type) entity already living
        # in a *different* document - see
        # EntityRepository.find_same_entity_elsewhere for why this is
        # exact-match rather than fuzzy. This is what lets
        # KnowledgeRetrievalService.find_cross_document_connections answer
        # "what do my documents say about X" across more than one document,
        # rather than each document's entity graph being an isolated island.
        for entity in entities:
            same_elsewhere = await self.entity_repository.find_same_entity_elsewhere(
                entity.name, entity.entity_type, exclude_document_id=document.id,
            )
            for other in same_elsewhere:
                await self.entity_repository.create_relationship(
                    entity.id, other.id, relationship_type="same_entity_across_documents",
                )

        return entities

    async def get_document(self, document_id: str) -> Optional[Document]:
        return await self.document_repository.get_by_id(document_id)

    async def list_documents(self, filters: DocumentFilterParams) -> List[Document]:
        return await self.document_repository.get_filtered(
            file_type=filters.file_type,
            source=filters.source,
            tag=filters.tag,
            skip=filters.skip,
            limit=filters.limit,
        )

    async def search_documents(self, query: str, file_type: Optional[str] = None, limit: int = 50) -> List[Document]:
        return await self.document_repository.search(query_str=query, file_type=file_type, limit=limit)

    async def update_document(self, document_id: str, update: DocumentUpdate) -> Optional[Document]:
        document = await self.document_repository.get_by_id(document_id)
        if not document:
            return None
        update_data = update.model_dump(exclude_unset=True)
        return await self.document_repository.update(document, update_data)

    async def delete_document(self, document_id: str) -> Optional[Document]:
        return await self.document_repository.soft_delete(document_id)

    async def get_entities_for_document(self, document_id: str) -> List[Entity]:
        return await self.entity_repository.get_by_document(document_id)
