import os
import glob
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from db import get_session
from models import DataSource
from auth import get_current_user

# Reuse vector store and helper from app
from app import vector_store, embeddings
from langchain_community.document_loaders import TextLoader, PyPDFLoader, WebBaseLoader
from langchain_core.documents import Document

router = APIRouter(prefix="/datasources", tags=["data"])

DATA_DIR = "data"  # ensure exists
os.makedirs(DATA_DIR, exist_ok=True)


class DataSourceOut(BaseModel):
    id: int
    source_type: str
    reference: str
    added_at: datetime
    last_synced_at: datetime | None = None

    class Config:
        orm_mode = True


@router.get("/", response_model=List[DataSourceOut])
def list_sources(
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    sources = session.exec(select(DataSource)).all()
    return sources


@router.post("/upload", response_model=DataSourceOut)
async def upload_file(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    # Save file
    dest_path = os.path.join(DATA_DIR, file.filename)
    with open(dest_path, "wb") as f:
        f.write(await file.read())

    # Create record
    ds = DataSource(source_type="file", reference=dest_path)
    session.add(ds)
    session.commit()
    session.refresh(ds)
    return ds


class UrlPayload(BaseModel):
    url: str


@router.post("/add-url", response_model=DataSourceOut)
def add_url(
    payload: UrlPayload,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    ds = DataSource(source_type="url", reference=payload.url)
    session.add(ds)
    session.commit()
    session.refresh(ds)
    return ds


@router.delete("/{source_id}")
def delete_source(
    source_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    ds = session.get(DataSource, source_id)
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource not found")

    # Remove file if exists
    if ds.source_type == "file" and os.path.exists(ds.reference):
        try:
            os.remove(ds.reference)
        except Exception:
            pass

    session.delete(ds)
    session.commit()

    # Rebuild vector store to ensure removed docs are gone
    rebuild_vector_store(session)

    return {"status": "deleted"}


@router.post("/{source_id}/sync")
def sync_source(
    source_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    ds = session.get(DataSource, source_id)
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource not found")

    documents: List[Document] = []
    try:
        if ds.source_type == "file":
            if ds.reference.lower().endswith(".txt"):
                loader = TextLoader(ds.reference, encoding="utf-8")
                documents.extend(loader.load())
            elif ds.reference.lower().endswith(".pdf"):
                loader = PyPDFLoader(ds.reference)
                documents.extend(loader.load())
            else:
                raise ValueError("Unsupported file type")
        elif ds.source_type == "url":
            loader = WebBaseLoader(ds.reference)
            documents.extend(loader.load())
        else:
            raise ValueError("Unsupported source type")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Add to vector store
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    if documents:
        if ds.reference.lower().endswith(".txt"):
            # simple char split as earlier
            splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=0)
            splits = splitter.split_documents(documents)
        else:
            splits = documents
        vector_store.add_documents(splits)

    # Mark as synced
    from datetime import datetime as _dt
    ds.last_synced_at = _dt.utcnow()
    session.add(ds)
    session.commit()

    return {"status": "synced", "added_docs": len(documents), "last_synced_at": ds.last_synced_at}


# Helper to rebuild FAISS index from all current sources (called after delete)
def rebuild_vector_store(session: Session):
    global vector_store
    # Reset index
    from langchain_community.vectorstores import FAISS
    import faiss
    from langchain_community.docstore.in_memory import InMemoryDocstore

    index = faiss.IndexFlatL2(len(embeddings.embed_query("test")))
    vector_store = FAISS(embedding_function=embeddings, index=index, docstore=InMemoryDocstore(), index_to_docstore_id={})

    # update reference in app module so chat endpoint uses fresh index
    import app as app_module
    app_module.vector_store = vector_store

    sources = session.exec(select(DataSource)).all()

    from langchain_text_splitters import RecursiveCharacterTextSplitter

    for src in sources:
        docs: List[Document] = []
        try:
            if src.source_type == "file":
                if src.reference.lower().endswith(".txt"):
                    loader = TextLoader(src.reference, encoding="utf-8")
                    docs.extend(loader.load())
                elif src.reference.lower().endswith(".pdf"):
                    loader = PyPDFLoader(src.reference)
                    docs.extend(loader.load())
            elif src.source_type == "url":
                loader = WebBaseLoader(src.reference)
                docs.extend(loader.load())
        except Exception:
            continue

        if docs:
            if src.reference.lower().endswith(".txt"):
                splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=0)
                splits = splitter.split_documents(docs)
            else:
                splits = docs
            vector_store.add_documents(splits)


@router.get("/{source_id}/preview")
def preview_source(
    source_id: int,
    session: Session = Depends(get_session),
):
    ds = session.get(DataSource, source_id)
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource not found")

    if ds.source_type == "file":
        if not os.path.exists(ds.reference):
            raise HTTPException(status_code=404, detail="File missing on disk")
        # For txt -> text/plain, for pdf -> application/pdf
        media_type = "text/plain" if ds.reference.lower().endswith(".txt") else "application/pdf"
        from fastapi.responses import FileResponse

        return FileResponse(ds.reference, media_type=media_type, filename=os.path.basename(ds.reference))
    elif ds.source_type == "url":
        # Redirect
        from fastapi.responses import RedirectResponse
        return RedirectResponse(ds.reference)
    else:
        raise HTTPException(status_code=400, detail="Unsupported source type") 