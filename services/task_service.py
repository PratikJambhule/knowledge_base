from datetime import date
from services.common import execute, query
from models.schemas import ActionItemInput, require_text
from utils.logging_config import log_event


def create_task(database_path: str, data: ActionItemInput, meeting_id: int | None = None, actor_id: int | None = None) -> int:
    title = require_text(data.title, "Task title")
    task_id = execute(
        database_path,
        """INSERT INTO tasks(handover_id,meeting_id,title,description,owner_id,due_date,priority)
           VALUES(?,?,?,?,?,?,?)""",
        (data.handover_id, meeting_id, title, data.description.strip(), data.owner_id,
         data.due_date.isoformat() if data.due_date else None, data.priority),
    )
    execute(database_path, "INSERT INTO task_history(task_id,event_type,new_value,actor_id) VALUES(?,?,?,?)",
            (task_id, "created", "Open", actor_id))
    log_event("task_created", entity_type="task", entity_id=task_id)
    return task_id


def list_tasks(database_path: str, search: str = ""):
    pattern = f"%{search.strip()}%"
    return query(
        database_path,
        """SELECT t.*, u.name owner_name, h.project_name, h.title handover_title
           FROM tasks t JOIN handovers h ON h.id=t.handover_id
           LEFT JOIN users u ON u.id=t.owner_id
           WHERE t.title LIKE ? OR COALESCE(t.description,'') LIKE ?
           ORDER BY CASE t.status WHEN 'Open' THEN 0 WHEN 'In Progress' THEN 1 ELSE 2 END, t.due_date""",
        (pattern, pattern),
    )


def update_task(database_path: str, task_id: int, status: str, owner_id: int | None, outcome: str, actor_id: int | None = None) -> None:
    valid_statuses = {"Open", "In Progress", "Blocked", "Completed", "Cancelled"}
    if status not in valid_statuses:
        raise ValueError("Invalid task status.")
    old = query(database_path, "SELECT status,owner_id FROM tasks WHERE id=?", (task_id,))
    if not old:
        raise ValueError("Task not found.")
    completed_at = "CURRENT_TIMESTAMP" if status == "Completed" else "NULL"
    execute(database_path, f"""UPDATE tasks SET status=?, owner_id=?, outcome=?,
        completed_at={completed_at}, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
        (status, owner_id, outcome.strip(), task_id))
    event_type = "reassigned" if old[0]["owner_id"] != owner_id else "updated"
    execute(database_path, "INSERT INTO task_history(task_id,event_type,old_value,new_value,note,actor_id) VALUES(?,?,?,?,?,?)",
            (task_id, event_type, f"{old[0]['status']} / {old[0]['owner_id']}", f"{status} / {owner_id}", outcome.strip(), actor_id))
    log_event("task_updated", entity_type="task", entity_id=task_id, status=status)
