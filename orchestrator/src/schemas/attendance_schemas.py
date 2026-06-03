import uuid

from pydantic import BaseModel, ConfigDict

from src.models.session_attendance import AttendanceStatus

class AttendanceUpdateItem(BaseModel):
    legislator_id: uuid.UUID
    status: AttendanceStatus

class AttendanceBulkUpdate(BaseModel):
    records: list[AttendanceUpdateItem]

class SessionAttendanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    legislative_session_id: uuid.UUID
    legislator_id: uuid.UUID
    status: AttendanceStatus
