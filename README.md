# KnowledgeBridge AI

KnowledgeBridge AI is a Streamlit application for person-to-person knowledge transfer when responsibilities move between employees. It combines transfer records, meetings, decisions, action items, documents, grounded AI answers and an explainable handover-readiness score.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app.py
```

Set `GEMINI_API_KEY` in `.env` or Streamlit Community Cloud secrets to enable Gemini features. The application remains usable without a key; AI actions show a clear configuration error and preserve manual-entry workflows.

## Architecture

- `pages/` contains Streamlit UI renderers.
- `services/` contains business workflows for handovers, tasks, meetings, documents, AI and readiness.
- `database/` owns SQLite initialization and parameterized persistence helpers.
- `models/` contains validated input objects.
- `utils/` contains structured file logging with correlation IDs.
- SQLite is the source of truth. ChromaDB is a rebuildable document index with SQLite fallback.

## AI workflows

Gemini can:

1. Extract a meeting summary and decisions from notes.
2. Suggest structured action items.
3. Generate an incoming employee's handover brief.
4. Answer questions using documents and task context for a selected handover.

AI output is advisory and should be reviewed before it is treated as authoritative. API failures preserve the source notes and are logged without secrets.

The service prefers the current `google-genai` client (`google.genai.Client`) and
has a compatibility fallback for the installed `google-generativeai` SDK. New
deployments should use `google-genai`; the older package is deprecated upstream.
Reusable prompts are in `services/prompts.py`. Structured responses are parsed
and validated before decisions or tasks can be saved.

## Person-to-person transfer workflow

Transfers begin in `Draft`, collect an outgoing and incoming employee, project,
date, scope and source material, and show an editable AI review before decisions
or action items are committed. Confirming the review moves the transfer to
`In Progress`. The details workspace supports `Pending Acceptance`, `Accepted`
and `Completed` states, incoming-employee briefs, evidence search, task
reassignment, stable task IDs, carry-forward history, outcomes and an
actor-attributed transfer timeline. The database seeds a Payments Platform
example so the workflow is demonstrable immediately.

Documents are extracted with PyMuPDF/python-docx, split into overlapping chunks,
and indexed in ChromaDB with filename, project, transfer ID and uploader metadata.
The assistant retrieves semantic evidence and cites its source metadata. If
ChromaDB is unavailable, the UI explicitly falls back to SQLite text search.

## Handover Readiness Score

The original feature combines task ownership/completion, document coverage, meeting continuity and decision coverage into an explainable 0–100 score. The details page shows the overall score and its supporting categories so a receiving employee can see what remains incomplete.

## Persistence and deployment

The app creates its SQLite schema automatically and seeds demo users on first startup. Uploaded files are stored under `data/uploads/`, the ChromaDB index under `data/chroma/`, and logs under `logs/`.

Streamlit Community Cloud has ephemeral local storage. For an assessment deployment, use seed/demo data and document this limitation. In production, move SQLite/file storage to persistent infrastructure while retaining the same service interfaces.

## Validation

The project has a focused service test:

```powershell
pytest -q
```

The application was also verified with `python -m compileall` and a Streamlit health request to `/_stcore/health`.
