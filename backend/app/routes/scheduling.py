from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.task import Task
from app.models.task_dependency import TaskDependency
from app.models.workflow import Workflow
from app.services.scheduler import calculate_schedule

router = APIRouter(
    prefix="/workflows",
    tags=["Scheduling"],
)


@router.post("/{workflow_id}/schedule")
def schedule_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
):
    workflow = db.get(Workflow, workflow_id)

    if workflow is None:
        raise HTTPException(
            status_code=404,
            detail="Workflow not found.",
        )

    tasks = db.scalars(
        select(Task)
        .where(Task.workflow_id == workflow_id)
        .order_by(Task.id)
    ).all()

    task_ids = [task.id for task in tasks]

    dependencies = []

    if task_ids:
        dependencies = db.scalars(
            select(TaskDependency).where(
                TaskDependency.task_id.in_(task_ids)
            )
        ).all()

    prerequisites_by_task = {
        task.id: [] for task in tasks
    }

    for dependency in dependencies:
        prerequisites_by_task[dependency.task_id].append(
            dependency.depends_on_task_id
        )

    scheduler_input = [
        {
            "id": task.id,
            "title": task.title,
            "estimated_hours": task.estimated_hours,
            "depends_on": prerequisites_by_task[task.id],
        }
        for task in tasks
    ]

    try:
        result = calculate_schedule(scheduler_input)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "workflow_id": workflow.id,
        "workflow_title": workflow.title,
        **result,
    }