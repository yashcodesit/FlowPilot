from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.task import Task
from app.models.workflow import Workflow
from app.schemas.task import TaskCreate, TaskResponse

router = APIRouter(
    prefix="/workflows/{workflow_id}/tasks",
    tags=["Tasks"],
)


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    workflow_id: int,
    task_data: TaskCreate,
    db: Session = Depends(get_db),
):
    workflow = db.get(Workflow, workflow_id)

    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found.",
        )

    title = task_data.title.strip()

    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task title cannot be empty.",
        )

    task = Task(
        workflow_id=workflow_id,
        title=title,
        description=task_data.description,
        priority=task_data.priority,
        estimated_hours=task_data.estimated_hours,
    )

    try:
        db.add(task)
        db.commit()
        db.refresh(task)
        return task
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create task.",
        ) from exc


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    workflow_id: int,
    db: Session = Depends(get_db),
):
    workflow = db.get(Workflow, workflow_id)

    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found.",
        )

    statement = (
        select(Task)
        .where(Task.workflow_id == workflow_id)
        .order_by(Task.created_at.asc())
    )

    return db.scalars(statement).all()