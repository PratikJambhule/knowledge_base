from datetime import date
from database.connection import initialize_database
from models.schemas import HandoverInput
from services.handover_service import create_handover, get_handover
from services.ai_service import AIServiceError, validate_extraction, extract_insights
from services.vector_service import chunk_text


def test_create_handover(tmp_path):
    db = str(tmp_path / "test.db")
    initialize_database(db)
    handover_id = create_handover(db, HandoverInput(1, 2, "Payments", date.today(), "API ownership", "Transfer payments ownership", ""))
    assert get_handover(db, handover_id)["project_name"] == "Payments"


def test_chunking_preserves_content():
    chunks = chunk_text("First paragraph.\n\nSecond paragraph.\n\nThird paragraph.", max_chars=25, overlap=5)
    assert chunks
    assert "First paragraph." in chunks[0]
    assert "Third paragraph." in chunks[-1]


def test_extraction_requires_configured_ai(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    try:
        extract_insights("", "test-model", "A note without credentials.")
    except AIServiceError as exc:
        assert "GEMINI_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected missing-key error")


def test_extraction_validation_keeps_unknowns_empty():
    result = validate_extraction({"summary": "Known summary", "action_items": [{"title": "Review", "owner_name": None}]})
    assert result["summary"] == "Known summary"
    assert result["action_items"][0]["due_date"] is None
