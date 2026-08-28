from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import Document
from app.models.entity import Entity, EntityType
from app.models.memory import Memory, MemoryType
from app.repositories.document_repository import DocumentRepository
from app.repositories.entity_repository import EntityRepository
from app.repositories.memory_repository import MemoryRepository
from app.retrieval.retrieval_service import extract_keywords
from app.knowledge.ranking import rank_documents
from app.core.config import settings


class KnowledgeRetrievalService:
    """Extends retrieval to imported documents and their extracted
    entities. Same "no vector DB" philosophy as RetrievalService
    (app/retrieval/retrieval_service.py): keyword matching against a real
    repository query, plus structured entity matches, then deterministic
    ranking - no embeddings anywhere.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.document_repository = DocumentRepository(db)
        self.entity_repository = EntityRepository(db)
        # Phase 9: only used by get_unified_timeline (merging entity-based
        # and memory-based timeline items) - see that method's docstring.
        self.memory_repository = MemoryRepository(db)

    async def retrieve_documents(self, message: str, limit: Optional[int] = None) -> List[Document]:
        limit = limit or settings.MAX_RETRIEVED_DOCUMENTS
        candidate_pool_size = max(limit * 4, 20)

        keywords = extract_keywords(message)
        candidates: List[Document] = []
        seen_ids = set()

        def _add(docs: List[Document]):
            for d in docs:
                if d.id not in seen_ids:
                    seen_ids.add(d.id)
                    candidates.append(d)

        for keyword in keywords:
            if len(candidates) >= candidate_pool_size:
                break
            _add(await self.document_repository.search(query_str=keyword, limit=candidate_pool_size))

        if not candidates:
            # Short queries ("my resume?") can produce zero significant
            # keywords after stopword filtering - fall back to the raw
            # message so a real match isn't missed.
            _add(await self.document_repository.search(query_str=message, limit=candidate_pool_size))

        entity_match_counts = await self._entity_match_counts(keywords)

        ranked = rank_documents(candidates, keywords=keywords, entity_match_counts=entity_match_counts)
        return ranked[:limit]

    async def _entity_match_counts(self, keywords: List[str]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for keyword in keywords:
            matches = await self.entity_repository.search(query_str=keyword, limit=50)
            for entity in matches:
                counts[entity.document_id] = counts.get(entity.document_id, 0) + 1
        return counts

    async def search_entities(self, query: str, entity_type: Optional[str] = None, limit: int = 50) -> List[Entity]:
        return await self.entity_repository.search(query_str=query, entity_type=entity_type, limit=limit)

    async def get_timeline(self, limit: int = 100) -> Dict[str, list]:
        """Chronological view over DEADLINE/TASK entities, for the Timeline
        tool/screen. Dates are stored as extractor-parsed best-effort ISO
        strings (see EntityExtractor) - entities where date parsing failed
        go in `undated` rather than being dropped or mis-sorted.
        """
        deadlines = await self.entity_repository.get_filtered(
            entity_type=EntityType.DEADLINE.value, limit=limit
        )
        tasks = await self.entity_repository.get_filtered(
            entity_type=EntityType.TASK.value, limit=limit
        )

        dated: List[Dict] = []
        undated: List[Dict] = []
        for entity in deadlines + tasks:
            parsed_date = (entity.details or {}).get("parsed_date")
            item = {
                "entity_id": entity.id,
                "entity_type": entity.entity_type,
                "name": entity.name,
                "document_id": entity.document_id,
                "date": parsed_date,
            }
            if parsed_date:
                dated.append(item)
            else:
                undated.append(item)

        dated.sort(key=lambda i: i["date"])
        return {"dated": dated, "undated": undated}

    async def find_cross_document_connections(self, entity_name: str, entity_type: Optional[str] = None) -> Dict:
        """Phase 9 / cross-document reasoning: every document that mentions
        an entity matching `entity_name` (case-insensitive; optionally
        narrowed by `entity_type`), plus what else each of those entities
        is directly related to (co-occurrence within its own document, and
        `same_entity_across_documents` links to other documents - see
        DocumentService._extract_and_link_entities).

        This answers "what do my documents say about X" across more than
        one document - e.g. "John Smith" mentioned in a meeting-notes
        document and again in an email export now surfaces as one
        connected picture instead of two unrelated hits from a plain
        keyword search.
        """
        matches = await self.entity_repository.get_filtered(
            entity_type=entity_type, name_contains=entity_name, limit=50
        )
        # get_filtered does a substring (name_contains) match; narrow to
        # entities whose name actually equals the query (case-insensitive) -
        # this is about connecting one specific named thing across
        # documents, not a broad fuzzy search (KnowledgeRetrievalService's
        # own retrieve_documents/search_entities already cover that case).
        exact_matches = [e for e in matches if e.name.strip().lower() == entity_name.strip().lower()]
        if not exact_matches:
            exact_matches = matches  # fall back to substring matches rather than reporting nothing

        documents_by_id: Dict[str, Document] = {}
        related_entities: List[Dict] = []
        seen_related_ids = set()

        for entity in exact_matches:
            document = await self.document_repository.get_by_id(entity.document_id)
            if document and document.id not in documents_by_id:
                documents_by_id[document.id] = document

            for relationship, other_id in await self.entity_repository.get_related(entity.id):
                if other_id in seen_related_ids:
                    continue
                seen_related_ids.add(other_id)
                other_entity = await self.entity_repository.get(other_id)
                if not other_entity:
                    continue
                related_entities.append({
                    "entity_id": other_entity.id,
                    "name": other_entity.name,
                    "entity_type": other_entity.entity_type,
                    "document_id": other_entity.document_id,
                    "relationship_type": relationship.relationship_type,
                })

        return {
            "query": entity_name,
            "matched_entities": [{"entity_id": e.id, "name": e.name, "entity_type": e.entity_type} for e in exact_matches],
            "documents": [{"id": d.id, "title": d.title} for d in documents_by_id.values()],
            "related_entities": related_entities,
            "spans_multiple_documents": len(documents_by_id) > 1,
        }

    async def get_unified_timeline(self, limit: int = 100, include_memories: bool = True) -> Dict[str, list]:
        """Phase 9: merges `get_timeline`'s document-entity-based items with
        memory-based TASK/EVENT items (created via chat - see
        MemoryExtractor rules 3, 5, 6 and app/skills/reminder_skill.py /
        calendar_skill.py) into one chronological view, tagged with
        `source` so a consumer can still tell them apart.

        Deliberately a NEW method, not a change to `get_timeline`'s
        existing return shape - `get_timeline` is used as-is by
        TimelineTool and (per docs/FolderStructure.md) the Android
        TimelineScreen/TimelineViewModel; changing its contract would be a
        breaking change for both with no guarantee that call site has been
        updated to match. This is additive: existing callers of
        `get_timeline` are entirely unaffected.
        """
        document_timeline = await self.get_timeline(limit=limit)
        dated: List[Dict] = [{**item, "source": "document"} for item in document_timeline["dated"]]
        undated: List[Dict] = [{**item, "source": "document"} for item in document_timeline["undated"]]

        if include_memories:
            task_memories = await self.memory_repository.get_filtered(memory_type=MemoryType.TASK.value, limit=limit)
            event_memories = await self.memory_repository.get_filtered(memory_type=MemoryType.EVENT.value, limit=limit)
            for memory in task_memories + event_memories:
                due = (memory.structured_data or {}).get("due_date") or (memory.structured_data or {}).get("date")
                item = {
                    "entity_id": memory.id,
                    "entity_type": memory.memory_type,
                    "name": memory.title,
                    "document_id": None,
                    "date": due,
                    "source": "memory",
                }
                (dated if due else undated).append(item)

        # Honesty note: document dates are extractor-parsed ISO strings
        # (see get_timeline's docstring) but memory due_date/date values are
        # free text from chat ("Friday", "next Monday" - see
        # MemoryExtractor.parse_reminder/parse_event, which don't attempt
        # date parsing). Sorting the merged list by raw string is therefore
        # true chronological order only for the document-sourced items;
        # memory-sourced items sort alphabetically among themselves. A
        # shared date parser for chat-extracted dates is a real gap, not
        # silently worked around here - see docs/Phase9_KnownLimitations.md.
        dated.sort(key=lambda i: i["date"] or "")
        return {"dated": dated, "undated": undated}
