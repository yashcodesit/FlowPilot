from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.task import TaskPriority

ExperienceLevel = Literal["beginner", "intermediate", "advanced"]


class WorkflowGenerateRequest(BaseModel):
    goal: str = Field(
        min_length=3,
        max_length=500,
        description="The primary objective or outcome to achieve.",
        examples=["Build and deploy a portfolio website"],
    )
    deadline_days: int | None = Field(
        default=None,
        gt=0,
        le=365,
        description="Optional deadline in calendar days from now (1 to 365 days).",
        examples=[10],
    )
    hours_per_day: float | None = Field(
        default=None,
        gt=0,
        le=24,
        description="Optional estimated daily hours dedicated to this workflow (up to 24).",
        examples=[2.0],
    )
    experience_level: ExperienceLevel = Field(
        default="intermediate",
        description="User's familiarity with the subject: beginner, intermediate, or advanced.",
    )
    additional_context: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional instructions, constraints, or preferences.",
        examples=["Include frontend development, testing, and deployment."],
    )

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Goal cannot be empty or whitespace-only.")
        return cleaned


class GeneratedTaskProposal(BaseModel):
    ref: str = Field(
        min_length=1,
        max_length=20,
        description="Temporary unique task reference ID (e.g., T1, T2).",
        examples=["T1"],
    )
    title: str = Field(
        min_length=1,
        max_length=200,
        description="Short, actionable title for the task.",
        examples=["Define website requirements"],
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Detailed description of what needs to be done.",
        examples=["Identify pages, content, and required features."],
    )
    priority: TaskPriority = Field(
        default="medium",
        description="Task priority: low, medium, high, or urgent.",
    )
    estimated_hours: float = Field(
        gt=0,
        description="Estimated duration in hours (must be positive).",
        examples=[2.0],
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="List of prerequisite task references that must complete before this task.",
        examples=[[]],
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Task title cannot be empty or whitespace-only.")
        return cleaned


class WorkflowProposal(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=200,
        description="Generated title for the proposed workflow.",
        examples=["Portfolio Website Launch"],
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="High-level overview of the proposed workflow.",
        examples=["Plan and launch a responsive portfolio website."],
    )
    tasks: list[GeneratedTaskProposal] = Field(
        min_length=1,
        max_length=30,
        description="List of generated tasks with references and dependencies.",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Workflow title cannot be empty or whitespace-only.")
        return cleaned


class ScheduledTaskItem(BaseModel):
    task_ref: str
    temporary_id: int
    title: str
    estimated_hours: float
    depends_on: list[str]
    earliest_start_hour: float
    earliest_finish_hour: float


class WorkflowGenerationResponse(BaseModel):
    proposal: WorkflowProposal
    schedule: list[ScheduledTaskItem]
    total_duration_hours: float
    deadline_warning: str | None = None
    is_persisted: bool = Field(
        default=False,
        description="Indicates that this proposal is for review only and has not been saved to the database.",
    )
    planning_assumptions: list[str] = Field(
        default_factory=lambda: [
            "Proposal is generated for review and has NOT been saved to the database.",
            "Schedule calculations assume linear elapsed work hours without calendar breaks or holidays.",
            "Tasks without mutual dependencies may execute in parallel if resources permit.",
        ]
    )

    model_config = ConfigDict(from_attributes=True)
