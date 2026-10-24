from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.generation import (
    ScheduledTaskItem,
    WorkflowGenerateRequest,
    WorkflowGenerationResponse,
)
from app.services.ai_generator import AIServiceError, WorkflowAIGenerator, get_ai_generator
from app.services.proposal_validator import ProposalValidationError, validate_proposal
from app.services.scheduler import calculate_schedule

router = APIRouter(
    prefix="/workflows",
    tags=["AI Workflow Generation"],
)


@router.post(
    "/generate",
    response_model=WorkflowGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a workflow proposal with AI",
    description=(
        "Converts a user's natural-language goal and planning constraints into a structured, "
        "dependency-aware workflow proposal with an estimated earliest-start schedule. "
        "This endpoint generates a proposal for user review and does NOT persist it to the database."
    ),
)
def generate_workflow(
    request: WorkflowGenerateRequest,
    ai_generator: WorkflowAIGenerator = Depends(get_ai_generator),
) -> WorkflowGenerationResponse:
    # 1. Generate structured proposal via AI service
    try:
        raw_proposal = ai_generator.generate_proposal(request)
    except AIServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        ) from exc

    # 2. Validate structural and relational integrity of proposal
    try:
        validated_proposal = validate_proposal(raw_proposal)
    except ProposalValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # 3. Prepare input for topological scheduling engine
    ref_to_id = {task.ref: idx + 1 for idx, task in enumerate(validated_proposal.tasks)}
    id_to_ref = {idx + 1: task.ref for idx, task in enumerate(validated_proposal.tasks)}

    scheduler_input = [
        {
            "id": ref_to_id[t.ref],
            "title": t.title,
            "estimated_hours": t.estimated_hours,
            "depends_on": [ref_to_id[dep] for dep in t.depends_on],
        }
        for t in validated_proposal.tasks
    ]

    try:
        schedule_result = calculate_schedule(scheduler_input)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Scheduling error: {str(exc)}",
        ) from exc

    # 4. Map schedule items back to task references
    scheduled_items: list[ScheduledTaskItem] = []
    for item in schedule_result["schedule"]:
        tid = item["task_id"]
        ref = id_to_ref[tid]
        scheduled_items.append(
            ScheduledTaskItem(
                task_ref=ref,
                temporary_id=tid,
                title=item["title"],
                estimated_hours=item["estimated_hours"],
                depends_on=[id_to_ref[pid] for pid in item["depends_on"]],
                earliest_start_hour=item["earliest_start_hour"],
                earliest_finish_hour=item["earliest_finish_hour"],
            )
        )

    total_duration = schedule_result["total_duration_hours"]

    # 5. Evaluate deadline feasibility
    deadline_warning = None
    if request.deadline_days is not None:
        hours_per_day = request.hours_per_day if request.hours_per_day is not None else 8.0
        available_hours = request.deadline_days * hours_per_day

        if total_duration > available_hours:
            deadline_warning = (
                f"Estimated schedule duration ({total_duration:.1f} hours) exceeds available planning time "
                f"({available_hours:.1f} hours, calculated as {request.deadline_days} days × {hours_per_day:.1f} hours/day). "
                f"Consider extending the deadline, increasing daily hours, or reducing task scope."
            )

    return WorkflowGenerationResponse(
        proposal=validated_proposal,
        schedule=scheduled_items,
        total_duration_hours=total_duration,
        deadline_warning=deadline_warning,
        is_persisted=False,
    )
