from models.schemas import MeetingInput, require_text
from services.common import execute, query
from utils.logging_config import log_event


def create_meeting(database_path: str, data: MeetingInput) -> int:
    meeting_id = execute(
        database_path,
        """INSERT INTO meetings(handover_id,title,meeting_date,agenda,notes,participants)
           VALUES(?,?,?,?,?,?)""",
        (data.handover_id, require_text(data.title, "Meeting title"), data.meeting_date.isoformat(),
         data.agenda.strip(), data.notes.strip(), data.participants.strip()),
    )
    log_event("meeting_created", entity_type="meeting", entity_id=meeting_id)
    return meeting_id


def list_meetings(database_path: str, handover_id: int | None = None):
    if handover_id:
        return query(database_path, "SELECT * FROM meetings WHERE handover_id=? ORDER BY meeting_date DESC", (handover_id,))
    return query(database_path, "SELECT m.*,h.project_name FROM meetings m JOIN handovers h ON h.id=m.handover_id ORDER BY meeting_date DESC")
