from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import Tool, ToolResult
from app.repositories.document_repository import DocumentRepository
from app.knowledge.knowledge_retrieval_service import KnowledgeRetrievalService
from app.knowledge.summarizer import extractive_summary


class SummaryTool(Tool):
    """Produces a deterministic extractive summary of a document - either a
    specific one by id, or the best keyword/entity match for a query. No
    LLM call: see app/knowledge/summarizer.py for the frequency-based
    extraction approach.
    """

    name = "summary"
    description = "Summarizes a specific document (by id) or the best-matching document for a query."

    def __init__(self, db: AsyncSession):
        self.document_repository = DocumentRepository(db)
        self.retrieval_service = KnowledgeRetrievalService(db)

    async def run(
        self, document_id: str = "", query: str = "", max_sentences: int = 3, **kwargs: Any
    ) -> ToolResult:
        try:
            document = None
            if document_id:
                document = await self.document_repository.get_by_id(document_id)
            elif query:
                matches = await self.retrieval_service.retrieve_documents(query, limit=1)
                document = matches[0] if matches else None

            if document is None:
                return ToolResult(
                    tool_name=self.name, success=False, output=None,
                    error="No matching document found to summarize.",
                )

            summary = extractive_summary(document.content, max_sentences=max_sentences)
            output = {"document_id": document.id, "title": document.title, "summary": summary}
            return ToolResult(tool_name=self.name, success=True, output=output)
        except Exception as e:
            return ToolResult(tool_name=self.name, success=False, output=None, error=str(e))
