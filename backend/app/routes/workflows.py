from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.workflow import Workflow
from app.schemas.workflow import WorkflowCreate, WorkflowResponse

router = APIRouter(prefix="/workflows", tags=["Workflows"])


@router.post(
    "",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workflow(
    workflow_data: WorkflowCreate,
    db: Session = Depends(get_db),
):
    try:
        workflow = Workflow(
            title=workflow_data.title.strip(),
            description=workflow_data.description,
        )

        if not workflow.title:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Workflow title cannot be empty.",
            )

        db.add(workflow)
        db.commit()
        db.refresh(workflow)

        return workflow

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create workflow.",
        ) from exc


@router.get("", response_model=list[WorkflowResponse])
def list_workflows(db: Session = Depends(get_db)):
    statement = select(Workflow).order_by(Workflow.created_at.desc())
    return db.scalars(statement).all()