import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.importers.document_importer import DocumentImporter
from app.importers.base import DocumentImportError
from app.services.document_service import DocumentService
from app.repositories.entity_repository import EntityRepository
from app.core.config import settings
from app.knowledge.knowledge_retrieval_service import KnowledgeRetrievalService
from app.knowledge.summarizer import multi_document_summary
from app.services.memory_service import MemoryService
from app.schemas.memory import MemoryCreate
from app.models.memory import MemoryType


@pytest.mark.asyncio
async def test_import_file_rejects_unsupported_extension(db_session: AsyncSession):
    importer = DocumentImporter(db_session)
    with pytest.raises(DocumentImportError):
        await importer.import_file("resume.docx", b"whatever bytes")


@pytest.mark.asyncio
async def test_import_file_rejects_oversized_file(db_session: AsyncSession, monkeypatch):
    monkeypatch.setattr(settings, "MAX_DOCUMENT_SIZE_MB", 0)  # anything at all is "too big"
    importer = DocumentImporter(db_session)
    with pytest.raises(DocumentImportError):
        await importer.import_file("notes.txt", b"small file content")


@pytest.mark.asyncio
async def test_import_file_persists_document_with_correct_metadata(db_session: AsyncSession):
    importer = DocumentImporter(db_session)
    document, was_created = await importer.import_file(
        "class_notes.txt", b"Lecture on distributed systems.", title="Class Notes", tags=["cs"], author="Me"
    )
    await db_session.commit()

    assert was_created is True
    assert document.title == "Class Notes"
    assert document.file_type == "txt"
    assert document.tags == ["cs"]
    assert document.author == "Me"
    assert document.size_bytes == len(b"Lecture on distributed systems.")
    assert document.content_hash  # sha256 hex digest, non-empty


@pytest.mark.asyncio
async def test_import_file_deduplicates_identical_content(db_session: AsyncSession):
    importer = DocumentImporter(db_session)
    raw = b"Identical content for dedup test."

    first, first_created = await importer.import_file("a.txt", raw)
    await db_session.commit()
    second, second_created = await importer.import_file("a_copy.txt", raw)
    await db_session.commit()

    assert first_created is True
    assert second_created is False
    assert first.id == second.id


@pytest.mark.asyncio
async def test_document_service_extracts_entities_on_new_import(db_session: AsyncSession):
    service = DocumentService(db_session)
    document = await service.import_document(
        "skills.txt", b"I know Python and Docker. TODO: update resume."
    )
    await db_session.commit()

    entities = await service.get_entities_for_document(document.id)
    entity_names = {e.name for e in entities}
    assert "Python" in entity_names
    assert "Docker" in entity_names


@pytest.mark.asyncio
async def test_document_service_does_not_duplicate_entities_on_reimport(db_session: AsyncSession):
    service = DocumentService(db_session)
    raw = b"I know Python and Docker."

    await service.import_document("skills.txt", raw)
    await db_session.commit()
    document_again = await service.import_document("skills_copy.txt", raw)
    await db_session.commit()

    entity_repo = EntityRepository(db_session)
    entities = await entity_repo.get_by_document(document_again.id)
    # Re-importing identical content is a dedup hit, not a new document, so
    # no second extraction pass should have run against it.
    python_entities = [e for e in entities if e.name == "Python"]
    assert len(python_entities) == 1


@pytest.mark.asyncio
async def test_document_service_creates_co_occurrence_relationships(db_session: AsyncSession):
    service = DocumentService(db_session)
    document = await service.import_document(
        "profile.md", b"# Profile\n\nProject: Atlas\n\nSkills: Python, Docker\n"
    )
    await db_session.commit()

    entities = await service.get_entities_for_document(document.id)
    assert len(entities) >= 2

    entity_repo = EntityRepository(db_session)
    related = await entity_repo.get_related(entities[0].id)
    assert len(related) >= 1


@pytest.mark.asyncio
async def test_document_service_soft_delete_hides_document(db_session: AsyncSession):
    service = DocumentService(db_session)
    document = await service.import_document("temp.txt", b"Temporary content to delete.")
    await db_session.commit()

    deleted = await service.delete_document(document.id)
    await db_session.commit()

    assert deleted is not None
    assert deleted.deleted_at is not None
    assert await service.get_document(document.id) is None


# --- Phase 9: cross-document entity linking ---------------------------------
@pytest.mark.asyncio
async def test_same_entity_linked_across_two_documents(db_session: AsyncSession):
    """Two unrelated documents that both mention 'Python' (a SKILL entity)
    should get a same_entity_across_documents relationship between their
    respective Python entities - the building block for
    KnowledgeRetrievalService.find_cross_document_connections."""
    service = DocumentService(db_session)
    doc_a = await service.import_document("resume.txt", b"I know Python and Docker.")
    await db_session.commit()
    doc_b = await service.import_document("cover_letter.txt", b"My strongest skill is Python.")
    await db_session.commit()

    entity_repo = EntityRepository(db_session)
    entities_a = await entity_repo.get_by_document(doc_a.id)
    python_a = next(e for e in entities_a if e.name == "Python")

    related = await entity_repo.get_related(python_a.id)
    cross_doc = [r for r, _ in related if r.relationship_type == "same_entity_across_documents"]
    assert len(cross_doc) == 1


@pytest.mark.asyncio
async def test_unrelated_entities_in_different_documents_are_not_cross_linked(db_session: AsyncSession):
    service = DocumentService(db_session)
    doc_a = await service.import_document("resume.txt", b"I know Python.")
    await db_session.commit()
    doc_b = await service.import_document("other.txt", b"I know Docker.")
    await db_session.commit()

    entity_repo = EntityRepository(db_session)
    entities_a = await entity_repo.get_by_document(doc_a.id)
    python_a = next(e for e in entities_a if e.name == "Python")

    related = await entity_repo.get_related(python_a.id)
    cross_doc = [r for r, _ in related if r.relationship_type == "same_entity_across_documents"]
    assert len(cross_doc) == 0


@pytest.mark.asyncio
async def test_find_cross_document_connections_reports_both_documents(db_session: AsyncSession):
    service = DocumentService(db_session)
    await service.import_document("resume.txt", b"I know Python and Docker.")
    await db_session.commit()
    await service.import_document("cover_letter.txt", b"My strongest skill is Python.")
    await db_session.commit()

    knowledge_service = KnowledgeRetrievalService(db_session)
    result = await knowledge_service.find_cross_document_connections("Python")

    assert result["spans_multiple_documents"] is True
    assert len(result["documents"]) == 2
    assert {d["title"] for d in result["documents"]} == {"resume.txt", "cover_letter.txt"}


@pytest.mark.asyncio
async def test_find_cross_document_connections_single_document_case(db_session: AsyncSession):
    service = DocumentService(db_session)
    await service.import_document("resume.txt", b"I know Python and Docker.")
    await db_session.commit()

    knowledge_service = KnowledgeRetrievalService(db_session)
    result = await knowledge_service.find_cross_document_connections("Python")

    assert result["spans_multiple_documents"] is False
    assert len(result["documents"]) == 1
    # Related entities from co-occurrence within that one document (Docker).
    assert any(r["name"] == "Docker" for r in result["related_entities"])


@pytest.mark.asyncio
async def test_find_cross_document_connections_no_match_returns_empty(db_session: AsyncSession):
    service = DocumentService(db_session)
    await service.import_document("resume.txt", b"I know Python and Docker.")
    await db_session.commit()

    knowledge_service = KnowledgeRetrievalService(db_session)
    result = await knowledge_service.find_cross_document_connections("Kubernetes")

    assert result["documents"] == []
    assert result["spans_multiple_documents"] is False


# --- Phase 9: unified timeline -----------------------------------------------
@pytest.mark.asyncio
async def test_unified_timeline_merges_document_and_memory_sources(db_session: AsyncSession):
    service = DocumentService(db_session)
    await service.import_document("deadlines.txt", b"Project due 2026-09-01.")
    await db_session.commit()

    memory_service = MemoryService(db_session)
    await memory_service.create_memory(MemoryCreate(
        title="Reminder: submit the report", content="Remind me to submit the report by Friday",
        memory_type=MemoryType.TASK, category="tasks", importance=4, is_pinned=False,
        source="chat", tags=["task"], structured_data={"task": "submit the report", "due_date": "Friday"},
    ))
    await db_session.commit()

    knowledge_service = KnowledgeRetrievalService(db_session)
    timeline = await knowledge_service.get_unified_timeline()

    sources = {item["source"] for item in timeline["dated"] + timeline["undated"]}
    assert "document" in sources
    assert "memory" in sources


@pytest.mark.asyncio
async def test_unified_timeline_excludes_memories_when_disabled(db_session: AsyncSession):
    service = DocumentService(db_session)
    await service.import_document("deadlines.txt", b"Project due 2026-09-01.")
    await db_session.commit()

    memory_service = MemoryService(db_session)
    await memory_service.create_memory(MemoryCreate(
        title="Reminder: submit the report", content="Remind me to submit the report by Friday",
        memory_type=MemoryType.TASK, category="tasks", importance=4, is_pinned=False,
        source="chat", tags=["task"], structured_data={"task": "submit the report", "due_date": "Friday"},
    ))
    await db_session.commit()

    knowledge_service = KnowledgeRetrievalService(db_session)
    timeline = await knowledge_service.get_unified_timeline(include_memories=False)

    sources = {item["source"] for item in timeline["dated"] + timeline["undated"]}
    assert sources == {"document"}


@pytest.mark.asyncio
async def test_get_timeline_unchanged_shape_after_unified_timeline_addition(db_session: AsyncSession):
    """Regression guard: get_timeline's own return shape/behavior must be
    completely unaffected by get_unified_timeline's addition."""
    service = DocumentService(db_session)
    await service.import_document("deadlines.txt", b"Project due 2026-09-01.")
    await db_session.commit()

    knowledge_service = KnowledgeRetrievalService(db_session)
    timeline = await knowledge_service.get_timeline()
    assert set(timeline.keys()) == {"dated", "undated"}
    for item in timeline["dated"]:
        assert "source" not in item  # get_timeline's items never carry a `source` key


# --- Phase 9: multi-document knowledge summary -------------------------------
@pytest.mark.asyncio
async def test_multi_document_summary_combines_multiple_documents(db_session: AsyncSession):
    service = DocumentService(db_session)
    doc_a = await service.import_document(
        "a.txt", b"Atlas is a personal AI assistant. It runs on FastAPI and Android."
    )
    doc_b = await service.import_document(
        "b.txt", b"Atlas uses a deterministic planner. It avoids fabricated data at all costs."
    )
    await db_session.commit()

    summary = multi_document_summary([doc_a, doc_b])
    assert "a.txt" in summary
    assert "b.txt" in summary


@pytest.mark.asyncio
async def test_multi_document_summary_empty_list_returns_empty_string():
    assert multi_document_summary([]) == ""
