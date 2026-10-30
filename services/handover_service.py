from datetime import date

from models.schemas import HandoverInput, require_text
from services.common import execute, query
from utils.logging_config import log_event


def create_handover(database_path: str, data: HandoverInput) -> int:
    if data.outgoing_user_id == data.incoming_user_id:
        raise ValueError("Outgoing and incoming employees must be different.")
    project = require_text(data.project_name, "Project")
    scope = require_text(data.transfer_scope, "Transfer scope")
    description = require_text(data.description, "Description")
    if not isinstance(data.transfer_date, date) or data.transfer_date.year < 2000:
        raise ValueError("Transfer date is invalid.")
    handover_id = execute(
        database_path,
        """INSERT INTO handovers(title,outgoing_user_id,incoming_user_id,project_name,transfer_date,
           transfer_scope,description,notes,status,created_by) VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (project + " knowledge transfer", data.outgoing_user_id, data.incoming_user_id, project,
         data.transfer_date.isoformat(), scope, description, data.notes.strip(), "Draft", data.outgoing_user_id),
    )
    execute(database_path, "INSERT INTO handover_history(handover_id,event_type,actor_id,details) VALUES(?,?,?,?)",
            (handover_id, "created", data.outgoing_user_id, f"Transfer created for {project}"))
    log_event("handover_created", entity_type="handover", entity_id=handover_id)
    return handover_id


def update_handover_status(database_path: str, handover_id: int, status: str, actor_id: int) -> None:
    allowed = {"Draft", "In Progress", "Pending Acceptance", "Accepted", "Completed"}
    if status not in allowed:
        raise ValueError("Invalid transfer state.")
    if not query(database_path, "SELECT id FROM handovers WHERE id=?", (handover_id,)):
        raise ValueError("Transfer not found.")
    if status == "Accepted":
        execute(database_path, "UPDATE handovers SET status=?,accepted_by=?,accepted_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, actor_id, handover_id))
    else:
        execute(database_path, "UPDATE handovers SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, handover_id))
    execute(database_path, "INSERT INTO handover_history(handover_id,event_type,actor_id,details) VALUES(?,?,?,?)",
            (handover_id, "status_changed", actor_id, f"Transfer moved to {status}"))
    log_event("handover_status_changed", entity_type="handover", entity_id=handover_id, status=status, actor_id=actor_id)


def list_handovers(database_path: str):
    return query(
        database_path,
        """SELECT h.*, o.name outgoing_name, i.name incoming_name
           FROM handovers h JOIN users o ON o.id=h.outgoing_user_id
           JOIN users i ON i.id=h.incoming_user_id ORDER BY h.updated_at DESC""",
    )


def get_handover(database_path: str, handover_id: int):
    rows = query(
        database_path,
        """SELECT h.*, o.name outgoing_name, i.name incoming_name
           FROM handovers h JOIN users o ON o.id=h.outgoing_user_id
           JOIN users i ON i.id=h.incoming_user_id WHERE h.id=?""",
        (handover_id,),
    )
    return rows[0] if rows else None
