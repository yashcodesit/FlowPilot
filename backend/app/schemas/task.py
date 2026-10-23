from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TaskPriority = Literal["low", "medium", "high", "urgent"]
TaskStatus = Literal["pending", "in_progress", "completed", "blocked"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    priority: TaskPriority = "medium"
    estimated_hours: float | None = Field(default=None, gt=0)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Task title cannot be empty or whitespace.")
        return cleaned


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    priority: TaskPriority | None = None
    estimated_hours: float | None = Field(default=None, gt=0)
    status: TaskStatus | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("Task title cannot be null.")
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Task title cannot be empty or whitespace.")
        return cleaned

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("Task priority cannot be null.")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("Task status cannot be null.")
        return v


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