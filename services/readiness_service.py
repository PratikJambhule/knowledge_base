from __future__ import annotations

from datetime import date

from services.common import execute, query


CATEGORIES = (
    ("project_overview", "Project Overview", 10),
    ("documentation", "Documentation", 25),
    ("decision_context", "Decision Context", 15),
    ("task_ownership", "Task Ownership", 20),
    ("deadlines", "Deadlines", 5),
    ("dependencies", "Dependencies", 15),
    ("risk_coverage", "Risk Coverage", 5),
    ("next_steps", "Next Steps", 5),
)


def calculate_readiness(database_path: str, handover_id: int) -> dict:
    handover_rows = query(database_path, "SELECT * FROM handovers WHERE id=?", (handover_id,))
    if not handover_rows:
        raise ValueError("Handover not found.")
    handover = handover_rows[0]
    documents = query(database_path, "SELECT title,extracted_text FROM documents WHERE handover_id=?", (handover_id,))
    meetings = query(database_path, "SELECT summary,notes FROM meetings WHERE handover_id=?", (handover_id,))
    decisions = query(database_path, "SELECT decision_text,rationale FROM decisions WHERE handover_id=?", (handover_id,))
    tasks = query(database_path, "SELECT title,description,owner_id,due_date,status FROM tasks WHERE handover_id=?", (handover_id,))
    source_text = " ".join(
        [handover["description"] or "", handover["notes"] or ""]
        + [d["extracted_text"] or "" for d in documents]
        + [m["summary"] or m["notes"] or "" for m in meetings]
    ).lower()

    evidence = {
        "project_overview": bool(handover["description"] and len(handover["description"].strip()) >= 40),
        "documentation": len(documents) > 0,
        "decision_context": bool(decisions and all(d["decision_text"] and (d["rationale"] or len(d["decision_text"]) >= 30) for d in decisions)),
        "task_ownership": bool(tasks) and all(t["owner_id"] is not None for t in tasks),
        "deadlines": bool(tasks) and all(t["due_date"] for t in tasks),
        "dependencies": any(word in source_text for word in ("depend", "blocked", "integration", "upstream", "downstream")),
        "risk_coverage": any(word in source_text for word in ("risk", "rollback", "incident", "failure", "mitigation")),
        "next_steps": bool(tasks),
    }
    categories = []
    missing = []
    recommendations = []
    for key, label, maximum in CATEGORIES:
        score = maximum if evidence[key] else 0
        categories.append({"key": key, "label": label, "score": score, "max": maximum, "supported": evidence[key]})
        if not evidence[key]:
            missing.append(label)
            recommendations.append(_recommendation(key))

    overall = sum(item["score"] for item in categories)
    warnings = []
    if any(t["status"] not in ("Completed", "Cancelled") and t["due_date"] and t["due_date"] < date.today().isoformat() for t in tasks):
        warnings.append("There are overdue unresolved tasks.")
    if any(t["owner_id"] is None for t in tasks):
        warnings.append("At least one task has no owner.")
    if not documents:
        warnings.append("No supporting documents are attached.")
    explanation = "Information is well covered." if overall >= 80 else "More context should be captured before independent takeover."
    execute(database_path, "UPDATE handovers SET readiness_score=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (overall, handover_id))
    return {
        "overall": overall,
        "categories": categories,
        "missing": missing,
        "warnings": warnings,
        "recommendations": recommendations,
        "explanation": explanation,
        "disclaimer": "This measures information completeness, not a guarantee of successful handover.",
    }


def _recommendation(key: str) -> str:
    return {
        "project_overview": "Add a clear project purpose, scope and current status.",
        "documentation": "Upload runbooks, architecture notes or relevant project documents.",
        "decision_context": "Record decisions with rationale and supporting context.",
        "task_ownership": "Assign an owner to every open task.",
        "deadlines": "Add due dates to all active tasks.",
        "dependencies": "Document upstream/downstream dependencies and blockers.",
        "risk_coverage": "Record operational risks, mitigations and rollback plans.",
        "next_steps": "Create explicit next-step tasks for the incoming employee.",
    }[key]
