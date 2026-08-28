from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import Tool, ToolResult
from app.knowledge.knowledge_retrieval_service import KnowledgeRetrievalService


class DocumentTool(Tool):
    """Finds imported documents relevant to a query - the document-system
    counterpart to MemoryTool. Keyword + entity based, no vector search."""

    name = "document"
    description = "Searches imported documents (PDF, Markdown, TXT, JSON, CSV) for content relevant to a query."

    def __init__(self, db: AsyncSession):
        self.retrieval_service = KnowledgeRetrievalService(db)

    async def run(self, query: str = "", limit: int = 5, **kwargs: Any) -> ToolResult:
        try:
            documents = await self.retrieval_service.retrieve_documents(query, limit=limit)
            output = [
                {
                    "id": d.id,
                    "title": d.title,
                    "file_type": d.file_type,
                    "snippet": (d.content or "")[:280],
                }
                for d in documents
            ]
            return ToolResult(tool_name=self.name, success=True, output=output)
        except Exception as e:
            return ToolResult(tool_name=self.name, success=False, output=None, error=str(e))
