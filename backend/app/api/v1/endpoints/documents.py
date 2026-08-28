from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.services.document_service import DocumentService
from app.importers.base import DocumentImportError
from app.parsers.base import ParserError
from app.schemas.document import DocumentResponse, DocumentSummary, DocumentUpdate, DocumentFilterParams
from app.schemas.entity import EntityResponse

router = APIRouter()


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # comma-separated; UploadFile forms can't carry a List[str] cleanly
    author: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    raw_bytes = await file.read()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    service = DocumentService(db)
    try:
        document = await service.import_document(
            filename=file.filename or "upload",
            raw_bytes=raw_bytes,
            title=title,
            tags=tag_list,
            author=author,
        )
        await db.commit()
        return document
    except (DocumentImportError, ParserError) as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=List[DocumentSummary])
async def list_documents(
    file_type: Optional[str] = None,
    source: Optional[str] = None,
    tag: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    filters = DocumentFilterParams(file_type=file_type, source=source, tag=tag, skip=skip, limit=limit)
    return await service.list_documents(filters)


@router.get("/search", response_model=List[DocumentSummary])
async def search_documents(
    q: str,
    file_type: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    return await service.search_documents(query=q, file_type=file_type, limit=limit)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    document = await service.get_document(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.get("/{document_id}/entities", response_model=List[EntityResponse])
async def get_document_entities(document_id: str, db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    document = await service.get_document(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return await service.get_entities_for_document(document_id)


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(document_id: str, update: DocumentUpdate, db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    document = await service.update_document(document_id, update)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    await db.commit()
    return document


@router.delete("/{document_id}", response_model=DocumentResponse)
async def delete_document(document_id: str, db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    document = await service.delete_document(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    await db.commit()
    return document
