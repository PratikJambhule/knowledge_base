from pathlib import Path
import hashlib

from services.common import execute, ensure_directories, query
from utils.logging_config import log_event


def extract_text(file_name: str, content: bytes) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".txt":
        return content.decode("utf-8", errors="replace")
    if suffix == ".pdf":
        try:
            import fitz
        except ImportError as exc:
            raise ValueError("PDF support is unavailable. Install PyMuPDF.") from exc
        document = fitz.open(stream=content, filetype="pdf")
        return "\n".join(page.get_text() for page in document)
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise ValueError("DOCX support is unavailable. Install python-docx.") from exc
        import io
        return "\n".join(paragraph.text for paragraph in Document(io.BytesIO(content)).paragraphs)
    raise ValueError("Only PDF, DOCX and TXT files are supported.")


def split_content(text: str, max_chars: int = 1800, overlap: int = 250) -> list[str]:
    from services.vector_service import chunk_text
    return chunk_text(text, max_chars=max_chars, overlap=overlap)


def save_document(
    database_path: str,
    upload_dir: str,
    handover_id: int | None,
    file_name: str,
    content: bytes,
    chroma_dir: str | None = None,
    uploader: str | None = None,
    project_name: str | None = None,
) -> int:
    text = extract_text(file_name, content).strip()
    if not text:
        raise ValueError("The uploaded document contains no readable text.")
    ensure_directories(upload_dir)
    digest = hashlib.sha256(content).hexdigest()
    safe_name = f"{digest[:16]}_{Path(file_name).name}"
    path = Path(upload_dir) / safe_name
    path.write_bytes(content)
    resolved_project = project_name
    if not resolved_project and handover_id:
        handover = query(database_path, "SELECT project_name FROM handovers WHERE id=?", (handover_id,))
        resolved_project = handover[0]["project_name"] if handover else None
    document_id = execute(database_path, """INSERT INTO documents(
        handover_id,title,file_name,file_type,storage_path,extracted_text,uploader,project_name)
        VALUES(?,?,?,?,?,?,?,?)""", (
        handover_id, Path(file_name).stem, file_name, Path(file_name).suffix.lower(),
        str(path), text, uploader or "unknown", resolved_project or "Global knowledge",
    ))
    if chroma_dir:
        from services.vector_service import VectorIndexUnavailable, index_document
        try:
            index_document(chroma_dir, document_id, text, {
                "document_id": document_id,
                "handover_id": handover_id or "global",
                "filename": file_name,
                "project": resolved_project or "Global knowledge",
                "uploader": uploader or "unknown",
            })
        except VectorIndexUnavailable:
            log_event("document_vector_index_skipped", entity_type="document", entity_id=document_id, outcome="unavailable")
    log_event("document_indexed", entity_type="document", entity_id=document_id)
    return document_id


def list_documents(database_path: str, handover_id: int | None = None):
    if handover_id:
        return query(database_path, "SELECT * FROM documents WHERE handover_id=? ORDER BY created_at DESC", (handover_id,))
    return query(database_path, "SELECT d.*,h.project_name FROM documents d LEFT JOIN handovers h ON h.id=d.handover_id ORDER BY d.created_at DESC")


def search_documents(database_path: str, search: str):
    return query(database_path, "SELECT * FROM documents WHERE extracted_text LIKE ? OR title LIKE ? ORDER BY created_at DESC",
                 (f"%{search}%", f"%{search}%"))
