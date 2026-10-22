from fastapi import APIRouter, Depends, HTTPException, status
from networkx import DiGraph, NetworkXNoCycle, find_cycle
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.task import Task
from app.models.task_dependency import TaskDependency
from app.schemas.dependency import DependencyCreate

router = APIRouter(
    prefix="/workflows/{workflow_id}/tasks/{task_id}/dependencies",
    tags=["Dependencies"],
)


def build_workflow_graph(db: Session, workflow_id: int) -> DiGraph:
    """Build the dependency graph for tasks in a workflow."""

    tasks = db.scalars(
        select(Task.id).where(Task.workflow_id == workflow_id)
    ).all()

    graph = DiGraph()
    graph.add_nodes_from(tasks)

    dependencies = db.execute(
        select(
            TaskDependency.task_id,
            TaskDependency.depends_on_task_id,
        ).where(
            TaskDependency.task_id.in_(tasks)
        )
    ).all()

    for task_id, depends_on_task_id in dependencies:
        graph.add_edge(depends_on_task_id, task_id)

    return graph


@router.post("", status_code=status.HTTP_201_CREATED)
def create_dependency(
    workflow_id: int,
    task_id: int,
    dependency_data: DependencyCreate,
    db: Session = Depends(get_db),
):
    task = db.get(Task, task_id)
    prerequisite = db.get(Task, dependency_data.depends_on_task_id)

    if task is None or task.workflow_id != workflow_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this workflow.",
        )

    if prerequisite is None or prerequisite.workflow_id != workflow_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dependency task not found in this workflow.",
        )

    prerequisite_id = dependency_data.depends_on_task_id

    if task_id == prerequisite_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A task cannot depend on itself.",
        )

    graph = build_workflow_graph(db, workflow_id)

    if graph.has_edge(prerequisite_id, task_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This dependency already exists.",
        )

    # A prerequisite must come before the task that depends on it.
    graph.add_edge(prerequisite_id, task_id)

    try:
        find_cycle(graph, orientation="original")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This dependency would create a cycle.",
        )
    except NetworkXNoCycle:
        pass

    dependency = TaskDependency(
        task_id=task_id,
        depends_on_task_id=prerequisite_id,
    )

    try:
        db.add(dependency)
        db.commit()
        db.refresh(dependency)

        return {
            "message": "Dependency created successfully.",
            "task_id": task_id,
            "depends_on_task_id": prerequisite_id,
        }

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create dependency.",
        ) from exc


@router.get("")
def list_dependencies(
    workflow_id: int,
    task_id: int,
    db: Session = Depends(get_db),
):
    task = db.get(Task, task_id)

    if task is None or task.workflow_id != workflow_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in this workflow.",
        )

    statement = select(TaskDependency).where(
        TaskDependency.task_id == task_id
    )

    dependencies = db.scalars(statement).all()

    return [
        {
            "task_id": item.task_id,
            "depends_on_task_id": item.depends_on_task_id,
        }
        for item in dependencies
    ]