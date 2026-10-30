from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from services.prompts import (
    ASSISTANT_PROMPT,
    CARRY_FORWARD_PROMPT,
    EXTRACTION_PROMPT,
    EXTRACTION_SYSTEM,
    HANDOVER_BRIEF_PROMPT,
    READINESS_GAP_PROMPT,
)
from utils.logging_config import log_event


class AIServiceError(RuntimeError):
    """A user-actionable AI failure; callers should preserve source data."""


@dataclass(frozen=True)
class AIResponse:
    text: str
    latency_ms: int
    model: str


EXTRACTION_DEFAULT: dict[str, Any] = {
    "summary": "",
    "key_topics": [],
    "decisions": [],
    "action_items": [],
    "suggested_owners": [],
    "deadlines": [],
    "dependencies": [],
    "risks": [],
    "unresolved_questions": [],
}


def get_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if key:
        return key
    try:
        import streamlit as st
        return str(st.secrets.get("GEMINI_API_KEY", "")).strip()
    except Exception:
        return ""


def _modern_client(api_key: str):
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except ImportError:
        return None


def _legacy_model(api_key: str, model_name: str):
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(model_name)
    except ImportError:
        return None


def _call_model(api_key: str, model_name: str, prompt: str) -> AIResponse:
    if not api_key:
        raise AIServiceError("Gemini is not configured. Set GEMINI_API_KEY or Streamlit secrets.")
    started = time.perf_counter()
    try:
        modern = _modern_client(api_key)
        if modern is not None:
            from google.genai import types
            response = modern.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json" if "JSON_ONLY" in prompt else "text/plain",
                    temperature=0.1,
                ),
            )
            text = (response.text or "").strip()
        else:
            legacy = _legacy_model(api_key, model_name)
            if legacy is None:
                raise AIServiceError("No supported Gemini SDK is installed. Install google-genai.")
            response = legacy.generate_content(
                prompt,
                generation_config={"temperature": 0.1, "response_mime_type": "application/json"}
                if "JSON_ONLY" in prompt else {"temperature": 0.1},
            )
            text = (getattr(response, "text", "") or "").strip()
        latency_ms = round((time.perf_counter() - started) * 1000)
        log_event("ai_call_completed", outcome="success", latency_ms=latency_ms, model=model_name)
        return AIResponse(text, latency_ms, model_name)
    except AIServiceError:
        raise
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000)
        error_name = type(exc).__name__
        log_event("ai_call_failed", outcome="error", latency_ms=latency_ms, model=model_name, error_type=error_name)
        if "429" in str(exc) or "rate" in str(exc).lower():
            raise AIServiceError("Gemini rate limit reached. Wait and try again.") from exc
        raise AIServiceError("Gemini request failed. Check connectivity and try again.") from exc


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AIServiceError("Gemini returned invalid structured data. Enter the information manually.") from exc
    if not isinstance(value, dict):
        raise AIServiceError("Gemini returned an unexpected structured response.")
    return value


def validate_extraction(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(EXTRACTION_DEFAULT)
    for key in result:
        if key in value:
            if key == "summary":
                if not isinstance(value[key], str):
                    raise AIServiceError("AI summary failed validation.")
                result[key] = value[key].strip()
            elif not isinstance(value[key], list):
                raise AIServiceError(f"AI field '{key}' failed validation.")
            else:
                result[key] = value[key]
    for item in result["action_items"]:
        if not isinstance(item, dict) or not item.get("title"):
            raise AIServiceError("AI action item failed validation.")
        item.setdefault("owner_name", None)
        item.setdefault("due_date", None)
        item.setdefault("dependencies", [])
        item.setdefault("risks", [])
    return result


def extract_insights(api_key: str | None, model_name: str, notes: str) -> dict[str, Any]:
    key = api_key or get_api_key()
    if not notes.strip():
        raise ValueError("Notes are required for AI extraction.")
    prompt = EXTRACTION_SYSTEM + "\nJSON_ONLY\n" + EXTRACTION_PROMPT.format(source=notes[:50000])
    response = _call_model(key, model_name, prompt)
    result = validate_extraction(_parse_json(response.text))
    log_event("ai_extraction_completed", outcome="success", latency_ms=response.latency_ms)
    return result


def generate_answer(api_key: str | None, model_name: str, question: str, evidence: str) -> str:
    if not question.strip():
        raise ValueError("Question is required.")
    if not evidence.strip():
        return "Evidence is insufficient to answer this question."
    response = _call_model(api_key or get_api_key(), model_name, ASSISTANT_PROMPT.format(
        question=question[:5000], evidence=evidence[:50000],
    ))
    return response.text or "Evidence is insufficient to answer this question."


def generate_handover_brief(api_key: str | None, model_name: str, incoming_employee: str, project: str, evidence: str) -> str:
    response = _call_model(api_key or get_api_key(), model_name, HANDOVER_BRIEF_PROMPT.format(
        incoming_employee=incoming_employee, project=project, evidence=evidence[:50000],
    ))
    return response.text


def generate_carry_forward_summary(api_key: str | None, model_name: str, records: str) -> str:
    if not records.strip():
        return "No unresolved records were supplied."
    response = _call_model(api_key or get_api_key(), model_name, CARRY_FORWARD_PROMPT.format(records=records[:50000]))
    return response.text


def extract_tasks(api_key: str | None, model_name: str, text: str) -> list[dict[str, Any]]:
    result = extract_insights(api_key, model_name, text)
    return result["action_items"]


def analyze_readiness_gaps(api_key: str | None, model_name: str, evidence: str) -> dict[str, list[str]]:
    if not evidence.strip():
        return {"missing_information": [], "critical_warnings": [], "recommendations": []}
    response = _call_model(
        api_key or get_api_key(),
        model_name,
        "JSON_ONLY\n" + READINESS_GAP_PROMPT.format(evidence=evidence[:50000]),
    )
    value = _parse_json(response.text)
    result = {}
    for key in ("missing_information", "critical_warnings", "recommendations"):
        items = value.get(key, [])
        if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
            raise AIServiceError("AI readiness analysis returned invalid evidence.")
        result[key] = items[:10]
    return result
