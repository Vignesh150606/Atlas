from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import or_
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models.entity import Entity, EntityRelationship
from app.models.document import Document


class EntityRepository(BaseRepository[Entity]):
    def __init__(self, db: AsyncSession):
        super().__init__(Entity, db)

    async def create_entity(self, obj_in: Dict[str, Any]) -> Entity:
        return await self.create(obj_in)

    async def get_by_document(self, document_id: str) -> List[Entity]:
        result = await self.db.execute(select(Entity).filter(Entity.document_id == document_id))
        return result.scalars().all()

    async def get_filtered(
        self,
        entity_type: Optional[str] = None,
        document_id: Optional[str] = None,
        name_contains: Optional[str] = None,
        skip: int = 0,
        limit: int = 200,
    ) -> List[Entity]:
        # Join against Document so entities belonging to a soft-deleted
        # document silently disappear too, without a separate deleted_at
        # column on Entity itself.
        query = select(Entity).join(Document, Entity.document_id == Document.id).filter(
            Document.deleted_at.is_(None)
        )
        if entity_type:
            query = query.filter(Entity.entity_type == entity_type)
        if document_id:
            query = query.filter(Entity.document_id == document_id)
        if name_contains:
            query = query.filter(Entity.name.ilike(f"%{name_contains}%"))

        query = query.order_by(Entity.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def search(self, query_str: str, entity_type: Optional[str] = None, limit: int = 50) -> List[Entity]:
        return await self.get_filtered(entity_type=entity_type, name_contains=query_str, limit=limit)

    async def find_same_entity_elsewhere(
        self, name: str, entity_type: str, exclude_document_id: str, limit: int = 10
    ) -> List[Entity]:
        """Phase 9 / cross-document reasoning: entities with the exact same
        name and type that live in a *different* document than
        `exclude_document_id` - the building block for linking "John Smith"
        mentioned in one document to "John Smith" mentioned in another.

        Deliberately exact-match (case-insensitive) on name+type, not a
        fuzzy/partial match - "Project Atlas" and "Project Atlas Phase 2"
        are related but not *the same* entity, and a looser match here
        would create a lot of low-value relationship noise. This mirrors
        the same precision-over-recall choice already made for
        `find_duplicate`'s exact-match fast path (see
        app/repositories/memory_repository.py).
        """
        query = select(Entity).join(Document, Entity.document_id == Document.id).filter(
            Document.deleted_at.is_(None),
            Entity.entity_type == entity_type,
            Entity.name.ilike(name.strip()),
            Entity.document_id != exclude_document_id,
        ).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_relationship(
        self, entity_a_id: int, entity_b_id: int, relationship_type: str = "co_occurs_in_document"
    ) -> Optional[EntityRelationship]:
        """Stores one row per unordered pair. Returns None (no-op) if the
        pair is identical (an entity can't relate to itself) or the
        relationship already exists, so re-processing a document doesn't
        pile up duplicate rows."""
        if entity_a_id == entity_b_id:
            return None

        source_id, target_id = sorted((entity_a_id, entity_b_id))

        existing = await self.db.execute(
            select(EntityRelationship).filter(
                EntityRelationship.source_entity_id == source_id,
                EntityRelationship.target_entity_id == target_id,
                EntityRelationship.relationship_type == relationship_type,
            )
        )
        if existing.scalars().first():
            return None

        relationship = EntityRelationship(
            source_entity_id=source_id,
            target_entity_id=target_id,
            relationship_type=relationship_type,
        )
        self.db.add(relationship)
        await self.db.flush()
        return relationship

    async def get_related(self, entity_id: int) -> List[Tuple[EntityRelationship, int]]:
        """Returns (relationship, other_entity_id) pairs for a given entity,
        regardless of which side of the pair it was stored on."""
        result = await self.db.execute(
            select(EntityRelationship).filter(
                or_(
                    EntityRelationship.source_entity_id == entity_id,
                    EntityRelationship.target_entity_id == entity_id,
                )
            )
        )
        relationships = result.scalars().all()
        pairs = []
        for rel in relationships:
            other_id = rel.target_entity_id if rel.source_entity_id == entity_id else rel.source_entity_id
            pairs.append((rel, other_id))
        return pairs
