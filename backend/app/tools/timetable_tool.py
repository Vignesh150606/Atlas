from typing import Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import Tool, ToolResult
from app.repositories.memory_repository import MemoryRepository
from app.models.memory import MemoryType
from app.retrieval.ranking import rank_memories


class TimetableTool(Tool):
    """Retrieves CLASS/TIMETABLE/EVENT memories.

    Deliberately does not attempt to compute "what's next chronologically" -
    schedule info is stored as free-text (e.g. "9am on Mondays") by the rule-
    based extractor, not as structured day/time values, so pretending to
    resolve "next class" precisely would be guessing. Instead this returns
    the relevant timetable memories, ranked, and lets the LLM reason over
    the actual stored schedule text when composing its answer.
    """

    name = "timetable"
    description = "Retrieves the user's stored class/timetable/event memories."

    _TIMETABLE_TYPES = [MemoryType.CLASS.value, MemoryType.TIMETABLE.value, MemoryType.EVENT.value]

    def __init__(self, db: AsyncSession):
        self.repository = MemoryRepository(db)

    async def run(self, limit: int = 10, **kwargs: Any) -> ToolResult:
        try:
            all_matches = []
            for memory_type in self._TIMETABLE_TYPES:
                all_matches.extend(await self.repository.get_filtered(memory_type=memory_type, limit=limit))

            ranked = rank_memories(all_matches, target_types=set(self._TIMETABLE_TYPES))
            output = [
                {
                    "title": m.title,
                    "content": m.content,
                    "memory_type": m.memory_type,
                    "structured_data": m.structured_data,
                }
                for m in ranked[:limit]
            ]
            return ToolResult(tool_name=self.name, success=True, output=output)
        except Exception as e:
            return ToolResult(tool_name=self.name, success=False, output=None, error=str(e))
