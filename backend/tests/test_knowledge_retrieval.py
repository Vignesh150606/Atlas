import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.document_service import DocumentService
from app.knowledge.knowledge_retrieval_service import KnowledgeRetrievalService


@pytest.mark.asyncio
async def test_retrieve_documents_finds_keyword_match(db_session: AsyncSession):
    service = DocumentService(db_session)
    await service.import_document("notes.txt", b"Notes about the Atlas mobile app architecture.")
    await service.import_document("recipe.txt", b"How to make a good omelette.")
    await db_session.commit()

    retrieval = KnowledgeRetrievalService(db_session)
    results = await retrieval.retrieve_documents("Tell me about the Atlas architecture")

    assert len(results) >= 1
    assert results[0].title == "notes.txt"


@pytest.mark.asyncio
async def test_retrieve_documents_ranks_entity_matches_higher(db_session: AsyncSession):
    service = DocumentService(db_session)
    # Both mention "project" in passing, but only one has it as a real extracted entity.
    await service.import_document("a.txt", b"Project: Atlas Mobile App is my main project this term.")
    await service.import_document("b.txt", b"I might start a side project eventually, who knows.")
    await db_session.commit()

    retrieval = KnowledgeRetrievalService(db_session)
    results = await retrieval.retrieve_documents("project")

    assert len(results) == 2
    assert results[0].title == "a.txt"  # the one with a real PROJECT entity should rank first


@pytest.mark.asyncio
async def test_retrieve_documents_returns_empty_list_when_nothing_imported(db_session: AsyncSession):
    retrieval = KnowledgeRetrievalService(db_session)
    results = await retrieval.retrieve_documents("anything at all")
    assert results == []


@pytest.mark.asyncio
async def test_get_timeline_separates_dated_and_undated_entities(db_session: AsyncSession):
    service = DocumentService(db_session)
    await service.import_document(
        "deadlines.txt", b"Assignment due 2026-09-01.\nTODO: read chapter 3."
    )
    await db_session.commit()

    retrieval = KnowledgeRetrievalService(db_session)
    timeline = await retrieval.get_timeline()

    assert any(item["date"] == "2026-09-01" for item in timeline["dated"])
    # "read chapter 3" is a task with no parseable date, so it belongs in undated.
    assert any("read chapter 3" in item["name"] for item in timeline["undated"])


@pytest.mark.asyncio
async def test_get_timeline_dated_items_are_sorted_chronologically(db_session: AsyncSession):
    service = DocumentService(db_session)
    await service.import_document("d1.txt", b"Final due 2026-12-01.")
    await service.import_document("d2.txt", b"First milestone due 2026-06-01.")
    await db_session.commit()

    retrieval = KnowledgeRetrievalService(db_session)
    timeline = await retrieval.get_timeline()

    dates = [item["date"] for item in timeline["dated"]]
    assert dates == sorted(dates)
