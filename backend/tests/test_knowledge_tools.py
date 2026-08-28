import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.document_service import DocumentService
from app.tools.document_tool import DocumentTool
from app.tools.knowledge_tool import KnowledgeTool
from app.tools.timeline_tool import TimelineTool
from app.tools.project_tool import ProjectTool
from app.tools.summary_tool import SummaryTool
from app.tools.router import ToolRouter


@pytest.mark.asyncio
async def test_document_tool_finds_relevant_document(db_session: AsyncSession):
    service = DocumentService(db_session)
    await service.import_document("notes.txt", b"Detailed notes about the Atlas retrieval pipeline.")
    await db_session.commit()

    tool = DocumentTool(db_session)
    result = await tool.run(query="Atlas retrieval pipeline")
    assert result.success
    assert any("notes.txt" == d["title"] for d in result.output)


@pytest.mark.asyncio
async def test_knowledge_tool_returns_documents_and_entities(db_session: AsyncSession):
    service = DocumentService(db_session)
    await service.import_document("skills.txt", b"I am skilled in Python and Docker.")
    await db_session.commit()

    tool = KnowledgeTool(db_session)
    result = await tool.run(query="Python")
    assert result.success
    assert len(result.output["documents"]) >= 1
    assert any(e["name"] == "Python" for e in result.output["entities"])


@pytest.mark.asyncio
async def test_timeline_tool_returns_dated_and_undated_sections(db_session: AsyncSession):
    service = DocumentService(db_session)
    await service.import_document("plan.txt", b"Final deadline is 2026-10-01.")
    await db_session.commit()

    tool = TimelineTool(db_session)
    result = await tool.run()
    assert result.success
    assert "dated" in result.output
    assert "undated" in result.output
    assert any(item["date"] == "2026-10-01" for item in result.output["dated"])


@pytest.mark.asyncio
async def test_project_tool_finds_project_and_related_entities(db_session: AsyncSession):
    service = DocumentService(db_session)
    await service.import_document(
        "atlas.md", b"# Atlas\n\nProject: Atlas\n\nSkills needed: Python, Docker\n"
    )
    await db_session.commit()

    tool = ProjectTool(db_session)
    result = await tool.run(query="Atlas")
    assert result.success
    assert len(result.output["projects"]) >= 1
    project = result.output["projects"][0]
    assert project["name"] == "Atlas"
    assert len(project["related"]) >= 1


@pytest.mark.asyncio
async def test_project_tool_returns_empty_list_when_no_match(db_session: AsyncSession):
    tool = ProjectTool(db_session)
    result = await tool.run(query="Nonexistent Project Name")
    assert result.success
    assert result.output["projects"] == []


@pytest.mark.asyncio
async def test_summary_tool_summarizes_by_document_id(db_session: AsyncSession):
    service = DocumentService(db_session)
    long_text = (
        b"Atlas is a personal AI assistant. It has a memory system that stores facts. "
        b"It also has a document import pipeline for PDFs and other formats. "
        b"The planner decides what information is needed before calling the provider. "
        b"Tools let ATLAS perform calculations and look up structured knowledge."
    )
    document = await service.import_document("overview.txt", long_text)
    await db_session.commit()

    tool = SummaryTool(db_session)
    result = await tool.run(document_id=document.id, max_sentences=2)
    assert result.success
    assert result.output["document_id"] == document.id
    assert len(result.output["summary"]) > 0
    assert len(result.output["summary"]) < len(long_text.decode())


@pytest.mark.asyncio
async def test_summary_tool_errors_cleanly_when_nothing_matches(db_session: AsyncSession):
    tool = SummaryTool(db_session)
    result = await tool.run(query="a document that does not exist")
    assert not result.success
    assert result.error


@pytest.mark.asyncio
async def test_router_dispatches_to_phase_6_tools(db_session: AsyncSession):
    router = ToolRouter(db_session)
    result = await router.dispatch("timeline")
    assert result.success
    assert "dated" in result.output
