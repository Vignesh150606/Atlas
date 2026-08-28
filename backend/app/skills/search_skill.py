"""Phase 9: SearchSkill.

"Search" in the Phase 9 skill examples means search over ATLAS's own
data (memories + imported documents) - there is no general web-search
capability configured anywhere in this codebase (no search-API key, no
network egress for it in the deployed backend), and building one as a stub
that returns nothing or fabricated results would violate this project's own
"no fake production code" standard. This is a unified front door over two
capabilities that already existed separately (MemoryTool / RetrievalService
and KnowledgeTool / KnowledgeRetrievalService) - one command, both sources,
one combined answer - rather than a third, parallel data source.
"""
import re
from typing import Any, Optional
from app.skills.base import Skill, SkillMatch
from app.skills.registry import register_skill
from app.tools.base import ToolResult
from app.retrieval.retrieval_service import RetrievalService
from app.knowledge.knowledge_retrieval_service import KnowledgeRetrievalService

_SEARCH_PATTERN = re.compile(
    r"\bsearch for ([^\.\!\?]+)|\bsearch my (?:notes|memories|documents) for ([^\.\!\?]+)|"
    r"\blook up ([^\.\!\?]+)|"
    r"\bfind (?:anything|any|info|information|notes|documents) (?:about|on|for) ([^\.\!\?]+)|"
    r"\bdo i have anything (?:about|on) ([^\.\!\?]+)",
    re.IGNORECASE,
)


@register_skill
class SearchSkill(Skill):
    name = "search"
    description = "Unified search across ATLAS's stored memories and imported documents (not the web)."

    def match(self, message: str) -> Optional[SkillMatch]:
        found = _SEARCH_PATTERN.search(message)
        if not found:
            return None
        query = next((g for g in found.groups() if g), "").strip()
        if not query:
            return None
        return SkillMatch(kwargs={"query": query}, confidence=0.8)

    async def run(self, query: str = "", **kwargs: Any) -> ToolResult:
        if not query.strip():
            return ToolResult(tool_name=self.name, success=False, output=None, error="No search query given.")

        memory_service = RetrievalService(self.db)
        knowledge_service = KnowledgeRetrievalService(self.db)

        memories = await memory_service.retrieve(query, limit=5, record_usage=False)
        documents = await knowledge_service.retrieve_documents(query, limit=5)

        if not memories and not documents:
            return ToolResult(
                tool_name=self.name, success=True,
                output=f"No memories or documents found matching '{query}'.",
            )

        output = {
            "query": query,
            "memories": [{"id": m.id, "title": m.title, "memory_type": m.memory_type} for m in memories],
            "documents": [{"id": d.id, "title": d.title} for d in documents],
        }
        return ToolResult(tool_name=self.name, success=True, output=output)
