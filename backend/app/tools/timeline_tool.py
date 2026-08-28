from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import Tool, ToolResult
from app.knowledge.knowledge_retrieval_service import KnowledgeRetrievalService


class TimelineTool(Tool):
    """Returns deadlines and tasks extracted from documents, in
    chronological order where a date could be parsed. Mirrors
    TimetableTool's philosophy: dates are extractor-parsed best-effort,
    not authoritative - entities that couldn't be date-parsed are returned
    separately (undated) rather than guessed at or dropped."""

    name = "timeline"
    description = "Returns extracted deadlines and tasks from imported documents, in chronological order."

    def __init__(self, db: AsyncSession):
        self.retrieval_service = KnowledgeRetrievalService(db)

    async def run(self, limit: int = 50, **kwargs: Any) -> ToolResult:
        try:
            timeline = await self.retrieval_service.get_timeline(limit=limit)
            return ToolResult(tool_name=self.name, success=True, output=timeline)
        except Exception as e:
            return ToolResult(tool_name=self.name, success=False, output=None, error=str(e))
