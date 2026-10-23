from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.task import Task
from app.models.workflow import Workflow
from app.schemas.task import (
    TaskCreate,
    TaskResponse,
    TaskStatusUpdate,
    TaskUpdate,
)

router = APIRouter(
    prefix="/workflows/{workflow_id}/tasks",
    tags=["Tasks"],
)


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create task",
    description="Create a new task within a workflow.",
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

    task = Task(
        workflow_id=workflow_id,
        title=task_data.title,
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


@router.get(
    "",
    response_model=list[TaskResponse],
    summary="List tasks",
    description="List all tasks belonging to a workflow.",
)
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


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get task details",
    description="Retrieve details of a specific task within a workflow.",
)
def get_task(
    workflow_id: int,
    task_id: int,
    db: Session = Depends(get_db),
):
    workflow = db.get(Workflow, workflow_id)

    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found.",
        )

    task = db.get(Task, task_id)

    if task is None or task.workflow_id != workflow_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this workflow.",
        )

    return task


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update task",
    description="Partially update fields of an existing task within a workflow.",
)
def update_task(
    workflow_id: int,
    task_id: int,
    task_data: TaskUpdate,
    db: Session = Depends(get_db),
):
    workflow = db.get(Workflow, workflow_id)

    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found.",
        )

    task = db.get(Task, task_id)

    if task is None or task.workflow_id != workflow_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this workflow.",
        )

    update_fields = task_data.model_dump(exclude_unset=True)

    for field, value in update_fields.items():
        setattr(task, field, value)

    try:
        db.commit()
        db.refresh(task)
        return task
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update task.",
        ) from exc


@router.patch(
    "/{task_id}/status",
    response_model=TaskResponse,
    summary="Update task status",
    description="Update the status of an existing task within a workflow.",
)
def update_task_status(
    workflow_id: int,
    task_id: int,
    status_data: TaskStatusUpdate,
    db: Session = Depends(get_db),
):
    workflow = db.get(Workflow, workflow_id)

    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found.",
        )

    task = db.get(Task, task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    if task.workflow_id != workflow_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this workflow.",
        )

    task.status = status_data.status

    try:
        db.commit()
        db.refresh(task)
        return task
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update task status.",
        ) from exc