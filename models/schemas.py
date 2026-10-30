from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class HandoverInput:
    outgoing_user_id: int
    incoming_user_id: int
    project_name: str
    transfer_date: date
    transfer_scope: str
    description: str
    notes: str


@dataclass(frozen=True)
class MeetingInput:
    handover_id: int
    title: str
    meeting_date: date
    agenda: str
    participants: str
    notes: str


@dataclass(frozen=True)
class ActionItemInput:
    handover_id: int
    title: str
    description: str
    owner_id: int | None
    due_date: date | None
    priority: str


def require_text(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field} is required.")
    if len(cleaned) > 5000:
        raise ValueError(f"{field} is too long.")
    return cleaned
