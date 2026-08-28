from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.tools.base import Tool, ToolResult
from app.repositories.entity_repository import EntityRepository
from app.models.entity import EntityType


class ProjectTool(Tool):
    """Finds PROJECT entities matching a name/query and everything related
    to them - other entities that co-occurred in the same source document
    (people, companies, tasks, deadlines, etc), via EntityRelationship.
    """

    name = "project"
    description = "Finds a project by name and returns entities related to it (people, tasks, deadlines, etc)."

    def __init__(self, db: AsyncSession):
        self.entity_repository = EntityRepository(db)

    async def run(self, query: str = "", limit: int = 10, **kwargs: Any) -> ToolResult:
        try:
            projects = await self.entity_repository.get_filtered(
                entity_type=EntityType.PROJECT.value, name_contains=query, limit=limit
            )
            if not projects:
                return ToolResult(tool_name=self.name, success=True, output={"projects": []})

            output = []
            for project in projects:
                related_pairs = await self.entity_repository.get_related(project.id)
                related_entities = []
                for _rel, other_id in related_pairs:
                    other = await self.entity_repository.get(other_id)
                    if other:
                        related_entities.append({
                            "id": other.id, "entity_type": other.entity_type, "name": other.name
                        })
                output.append({
                    "id": project.id,
                    "name": project.name,
                    "document_id": project.document_id,
                    "related": related_entities,
                })

            return ToolResult(tool_name=self.name, success=True, output={"projects": output})
        except Exception as e:
            return ToolResult(tool_name=self.name, success=False, output=None, error=str(e))
