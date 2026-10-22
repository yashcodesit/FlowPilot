from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    estimated_hours: float | None = Field(default=None, gt=0)


class TaskResponse(BaseModel):
    id: int
    workflow_id: int
    title: str
    description: str | None
    status: str
    priority: str
    estimated_hours: float | None
    due_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)