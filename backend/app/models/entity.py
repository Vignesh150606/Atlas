from enum import Enum
from sqlalchemy import Column, String, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import TimestampModel


class EntityType(str, Enum):
    PERSON = "person"
    PROJECT = "project"
    COMPANY = "company"
    COURSE = "course"
    TOPIC = "topic"
    TASK = "task"
    DEADLINE = "deadline"
    SKILL = "skill"


class Entity(TimestampModel):
    """A structured fact pulled out of an imported document by
    EntityExtractor (deterministic, rule-based - see
    app/extraction/entity_extractor.py, no ML/embeddings involved).

    Always belongs to exactly one document. There's no soft-delete on
    Entity itself: it's derivative data, so it's excluded from queries by
    joining against Document.deleted_at instead of duplicating that
    bookkeeping here (see EntityRepository).
    """
    __tablename__ = "entities"

    entity_type = Column(String, nullable=False, index=True)  # EntityType value
    name = Column(String, nullable=False, index=True)  # canonical extracted text, e.g. "John Smith", "CS 101"
    details = Column(JSON, nullable=False, default=dict)  # extraction-specific extras (e.g. raw date text for a deadline)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    confidence = Column(Integer, nullable=False, default=70)  # 0-100, rule-based heuristic score, not a model probability

    document = relationship("Document")


class EntityRelationship(TimestampModel):
    """A link between two entities. Phase 6 only creates one relationship
    kind automatically: entities extracted from the same document are
    related as 'co_occurs_in_document' - a simple, deterministic proxy for
    "these are probably connected" without any relation-extraction ML.

    Stored once per unordered pair (source_entity_id < target_entity_id)
    to avoid duplicate reverse rows; callers look up relationships for an
    entity by matching either column (see EntityRepository.get_related).
    """
    __tablename__ = "entity_relationships"

    source_entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    target_entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String, nullable=False, default="co_occurs_in_document", index=True)

    source_entity = relationship("Entity", foreign_keys=[source_entity_id])
    target_entity = relationship("Entity", foreign_keys=[target_entity_id])
