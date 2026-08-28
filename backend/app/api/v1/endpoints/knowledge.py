from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.knowledge.knowledge_retrieval_service import KnowledgeRetrievalService
from app.repositories.entity_repository import EntityRepository
from app.schemas.entity import EntityResponse

router = APIRouter()


@router.get("/entities", response_model=List[EntityResponse])
async def list_entities(
    entity_type: Optional[str] = None,
    document_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
):
    repository = EntityRepository(db)
    return await repository.get_filtered(
        entity_type=entity_type, document_id=document_id, skip=skip, limit=limit
    )


@router.get("/search")
async def search_knowledge(
    q: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Unified search across imported documents and extracted entities -
    the same combined view KnowledgeTool returns to the LLM, exposed
    directly for the Android Search screen."""
    service = KnowledgeRetrievalService(db)
    documents = await service.retrieve_documents(q, limit=limit)
    entities = await service.search_entities(q, limit=limit * 2)
    return {
        "documents": [
            {"id": d.id, "title": d.title, "file_type": d.file_type, "snippet": (d.content or "")[:280]}
            for d in documents
        ],
        "entities": [
            {"id": e.id, "entity_type": e.entity_type, "name": e.name, "document_id": e.document_id}
            for e in entities
        ],
    }


@router.get("/timeline")
async def get_timeline(limit: int = 100, db: AsyncSession = Depends(get_db)) -> Dict[str, list]:
    service = KnowledgeRetrievalService(db)
    return await service.get_timeline(limit=limit)
