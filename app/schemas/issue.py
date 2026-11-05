from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.site_issue import IssueStatus


class IssueCreate(BaseModel):
    title: str = Field(..., min_length=4, max_length=80)
    detail: str = Field(..., min_length=10, max_length=1000)


class IssueRead(BaseModel):
    id: int
    title: str
    detail: str
    status: IssueStatus
    created_at: datetime | None = None
    solved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class IssueAdminRead(IssueRead):
    user_name: str
    user_email: str
