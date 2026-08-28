from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import Tool, ToolResult
from app.retrieval.retrieval_service import RetrievalService


class MemoryTool(Tool):
    """Thin tool wrapper around RetrievalService, for when the Planner
    decides a memory lookup is the whole job (e.g. a MEMORY_SEARCH intent)
    rather than just prompt-context enrichment.
    """

    name = "memory"
    description = "Searches ATLAS's stored memories for content relevant to a query."

    def __init__(self, db: AsyncSession):
        self.retrieval_service = RetrievalService(db)

    async def run(self, query: str = "", limit: int = 5, **kwargs: Any) -> ToolResult:
        try:
            memories = await self.retrieval_service.retrieve(query, limit=limit, record_usage=False)
            output = [
                {"id": m.id, "title": m.title, "content": m.content, "memory_type": m.memory_type}
                for m in memories
            ]
            return ToolResult(tool_name=self.name, success=True, output=output)
        except Exception as e:
            return ToolResult(tool_name=self.name, success=False, output=None, error=str(e))
