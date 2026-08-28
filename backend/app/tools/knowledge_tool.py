from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import Tool, ToolResult
from app.knowledge.knowledge_retrieval_service import KnowledgeRetrievalService


class KnowledgeTool(Tool):
    """Broader than DocumentTool: returns both matching documents AND the
    structured entities (people, projects, companies, courses, topics,
    tasks, deadlines, skills) found within them, for questions that are
    really about a fact rather than "find me a file"."""

    name = "knowledge"
    description = "Searches both imported documents and the structured entities extracted from them."

    def __init__(self, db: AsyncSession):
        self.retrieval_service = KnowledgeRetrievalService(db)

    async def run(self, query: str = "", limit: int = 5, **kwargs: Any) -> ToolResult:
        try:
            documents = await self.retrieval_service.retrieve_documents(query, limit=limit)
            entities = await self.retrieval_service.search_entities(query, limit=limit * 2)
            output = {
                "documents": [
                    {"id": d.id, "title": d.title, "file_type": d.file_type, "snippet": (d.content or "")[:200]}
                    for d in documents
                ],
                "entities": [
                    {"id": e.id, "entity_type": e.entity_type, "name": e.name, "document_id": e.document_id}
                    for e in entities
                ],
            }
            return ToolResult(tool_name=self.name, success=True, output=output)
        except Exception as e:
            return ToolResult(tool_name=self.name, success=False, output=None, error=str(e))
