import pytest
from sqlalchemy import select

from app.main import app
from app.models.task import Task
from app.models.task_dependency import TaskDependency
from app.models.workflow import Workflow
from app.schemas.generation import (
    GeneratedTaskProposal,
    WorkflowProposal,
)
from app.services.ai_generator import (
    AIParsingError,
    AIProviderError,
    AIRateLimitError,
    AIServiceNotConfiguredError,
    AITimeoutError,
    WorkflowAIGenerator,
    get_ai_generator,
)


class FakeAIGenerator(WorkflowAIGenerator):
    """Deterministic fake AI generator for unit and integration testing."""

    def __init__(self, proposal: WorkflowProposal | None = None, error: Exception | None = None):
        self.proposal = proposal
        self.error = error

    def generate_proposal(self, request):
        if self.error:
            raise self.error
        if self.proposal:
            return self.proposal
        raise ValueError("Neither proposal nor error was configured on FakeAIGenerator.")


@pytest.fixture
def valid_proposal():
    """A realistic, valid workflow proposal fixture."""
    return WorkflowProposal(
        title="Portfolio Website Launch",
        description="Plan and launch a responsive portfolio website.",
        tasks=[
            GeneratedTaskProposal(
                ref="T1",
                title="Define website requirements",
                description="Identify pages, content, and required features.",
                priority="high",
                estimated_hours=2.0,
                depends_on=[],
            ),
            GeneratedTaskProposal(
                ref="T2",
                title="Design UI mockups",
                description="Create wireframes for homepage and project pages.",
                priority="medium",
                estimated_hours=3.0,
                depends_on=["T1"],
            ),
            GeneratedTaskProposal(
                ref="T3",
                title="Develop frontend",
                description="Implement pages using HTML/CSS/JS.",
                priority="high",
                estimated_hours=5.0,
                depends_on=["T2"],
            ),
            GeneratedTaskProposal(
                ref="T4",
                title="Deploy and test",
                description="Deploy to hosting platform and run tests.",
                priority="urgent",
                estimated_hours=2.0,
                depends_on=["T3"],
            ),
        ],
    )


# ============================================================================
# 1. Request Schema and Validation Tests
# ============================================================================

def test_valid_request_schema(client, valid_proposal):
    """1. Test valid request schema produces 200 OK and expected structure."""
    fake_generator = FakeAIGenerator(proposal=valid_proposal)
    app.dependency_overrides[get_ai_generator] = lambda: fake_generator

    response = client.post(
        "/workflows/generate",
        json={
            "goal": "Build and deploy a portfolio website",
            "deadline_days": 10,
            "hours_per_day": 4,
            "experience_level": "intermediate",
            "additional_context": "Include testing and deployment.",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["proposal"]["title"] == "Portfolio Website Launch"
    assert len(data["proposal"]["tasks"]) == 4
    assert data["total_duration_hours"] == 12.0
    assert data["is_persisted"] is False
    assert len(data["schedule"]) == 4


def test_empty_goal_rejection(client):
    """2. Test that empty or whitespace-only goal is rejected with 422."""
    # Empty string
    r1 = client.post("/workflows/generate", json={"goal": ""})
    assert r1.status_code == 422

    # Whitespace only
    r2 = client.post("/workflows/generate", json={"goal": "   \n\t  "})
    assert r2.status_code == 422


def test_invalid_deadline_rejection(client):
    """3. Test that non-positive or excessive deadline is rejected with 422."""
    # Zero
    r1 = client.post("/workflows/generate", json={"goal": "Build an app", "deadline_days": 0})
    assert r1.status_code == 422

    # Negative
    r2 = client.post("/workflows/generate", json={"goal": "Build an app", "deadline_days": -5})
    assert r2.status_code == 422

    # Exceeds maximum 365
    r3 = client.post("/workflows/generate", json={"goal": "Build an app", "deadline_days": 400})
    assert r3.status_code == 422


def test_invalid_hours_per_day_rejection(client):
    """4. Test that non-positive or excessive daily hours are rejected with 422."""
    # Zero
    r1 = client.post("/workflows/generate", json={"goal": "Build an app", "hours_per_day": 0})
    assert r1.status_code == 422

    # Negative
    r2 = client.post("/workflows/generate", json={"goal": "Build an app", "hours_per_day": -1})
    assert r2.status_code == 422

    # Exceeds 24
    r3 = client.post("/workflows/generate", json={"goal": "Build an app", "hours_per_day": 25})
    assert r3.status_code == 422


# ============================================================================
# 2. Dependency and Proposal Validation Tests
# ============================================================================

def test_valid_generated_proposal(client, valid_proposal):
    """5. Test that a valid generated proposal passes all validation checks."""
    app.dependency_overrides[get_ai_generator] = lambda: FakeAIGenerator(proposal=valid_proposal)

    response = client.post("/workflows/generate", json={"goal": "Build portfolio"})
    assert response.status_code == 200
    data = response.json()
    assert data["proposal"]["title"] == "Portfolio Website Launch"


def test_duplicate_task_reference_rejection(client):
    """6. Reject proposals with duplicate task references."""
    invalid_proposal = WorkflowProposal(
        title="Invalid Duplicate",
        tasks=[
            GeneratedTaskProposal(
                ref="T1",
                title="Task One",
                estimated_hours=2.0,
            ),
            GeneratedTaskProposal(
                ref="T1",  # Duplicate ref
                title="Task Two",
                estimated_hours=3.0,
            ),
        ],
    )
    app.dependency_overrides[get_ai_generator] = lambda: FakeAIGenerator(proposal=invalid_proposal)

    response = client.post("/workflows/generate", json={"goal": "Build portfolio"})
    assert response.status_code == 422
    assert "Duplicate task reference" in response.json()["detail"]


def test_unknown_dependency_rejection(client):
    """7. Reject proposals referencing nonexistent tasks in depends_on."""
    invalid_proposal = WorkflowProposal(
        title="Invalid Unknown Dep",
        tasks=[
            GeneratedTaskProposal(
                ref="T1",
                title="Task One",
                estimated_hours=2.0,
                depends_on=["T99"],  # Nonexistent
            ),
        ],
    )
    app.dependency_overrides[get_ai_generator] = lambda: FakeAIGenerator(proposal=invalid_proposal)

    response = client.post("/workflows/generate", json={"goal": "Build portfolio"})
    assert response.status_code == 422
    assert "depends on unknown task reference" in response.json()["detail"]


def test_self_dependency_rejection(client):
    """8. Reject proposals where a task depends on itself."""
    invalid_proposal = WorkflowProposal(
        title="Invalid Self Dep",
        tasks=[
            GeneratedTaskProposal(
                ref="T1",
                title="Task One",
                estimated_hours=2.0,
                depends_on=["T1"],  # Self-dependency
            ),
        ],
    )
    app.dependency_overrides[get_ai_generator] = lambda: FakeAIGenerator(proposal=invalid_proposal)

    response = client.post("/workflows/generate", json={"goal": "Build portfolio"})
    assert response.status_code == 422
    assert "cannot depend on itself" in response.json()["detail"]


def test_cyclic_dependency_rejection(client):
    """9. Reject proposals containing dependency cycles."""
    invalid_proposal = WorkflowProposal(
        title="Cyclic Proposal",
        tasks=[
            GeneratedTaskProposal(
                ref="T1",
                title="Task 1",
                estimated_hours=2.0,
                depends_on=["T2"],
            ),
            GeneratedTaskProposal(
                ref="T2",
                title="Task 2",
                estimated_hours=3.0,
                depends_on=["T1"],
            ),
        ],
    )
    app.dependency_overrides[get_ai_generator] = lambda: FakeAIGenerator(proposal=invalid_proposal)

    response = client.post("/workflows/generate", json={"goal": "Build portfolio"})
    assert response.status_code == 422
    assert "Dependency cycle detected" in response.json()["detail"]


def test_invalid_task_duration_rejection(client):
    """10. Reject task duration <= 0 at schema and service layers."""
    with pytest.raises(Exception):
        GeneratedTaskProposal(
            ref="T1",
            title="Task 1",
            estimated_hours=0.0,
        )

    with pytest.raises(Exception):
        GeneratedTaskProposal(
            ref="T1",
            title="Task 1",
            estimated_hours=-2.0,
        )


def test_invalid_priority_rejection(client):
    """11. Reject unsupported priority values at schema layer."""
    with pytest.raises(Exception):
        GeneratedTaskProposal(
            ref="T1",
            title="Task 1",
            estimated_hours=2.0,
            priority="ultra_high",
        )


# ============================================================================
# 3. Scheduling and Deadline Integration Tests
# ============================================================================

def test_scheduling_integration(client, valid_proposal):
    """12. Verify topological earliest start and finish times calculation."""
    app.dependency_overrides[get_ai_generator] = lambda: FakeAIGenerator(proposal=valid_proposal)

    response = client.post("/workflows/generate", json={"goal": "Build portfolio"})
    assert response.status_code == 200
    data = response.json()

    schedule = {item["task_ref"]: item for item in data["schedule"]}
    assert schedule["T1"]["earliest_start_hour"] == 0.0
    assert schedule["T1"]["earliest_finish_hour"] == 2.0

    assert schedule["T2"]["earliest_start_hour"] == 2.0
    assert schedule["T2"]["earliest_finish_hour"] == 5.0

    assert schedule["T3"]["earliest_start_hour"] == 5.0
    assert schedule["T3"]["earliest_finish_hour"] == 10.0

    assert schedule["T4"]["earliest_start_hour"] == 10.0
    assert schedule["T4"]["earliest_finish_hour"] == 12.0

    assert data["total_duration_hours"] == 12.0


def test_deadline_exceeded_warning(client, valid_proposal):
    """13. Produce a clear warning when calculated duration exceeds available planning time."""
    app.dependency_overrides[get_ai_generator] = lambda: FakeAIGenerator(proposal=valid_proposal)

    # 12 hours total duration vs (2 days * 4 hours/day = 8 hours available) -> Exceeded!
    r_exceeded = client.post(
        "/workflows/generate",
        json={
            "goal": "Build portfolio",
            "deadline_days": 2,
            "hours_per_day": 4.0,
        },
    )
    assert r_exceeded.status_code == 200
    data_exceeded = r_exceeded.json()
    assert data_exceeded["deadline_warning"] is not None
    assert "exceeds available planning time" in data_exceeded["deadline_warning"]

    # 12 hours total duration vs (10 days * 4 hours/day = 40 hours available) -> Feasible!
    r_feasible = client.post(
        "/workflows/generate",
        json={
            "goal": "Build portfolio",
            "deadline_days": 10,
            "hours_per_day": 4.0,
        },
    )
    assert r_feasible.status_code == 200
    data_feasible = r_feasible.json()
    assert data_feasible["deadline_warning"] is None


# ============================================================================
# 4. Provider and Error Handling Tests
# ============================================================================

def test_missing_api_configuration(client):
    """14. Return 503 explaining AI generation is not configured when key is missing."""
    app.dependency_overrides[get_ai_generator] = lambda: FakeAIGenerator(
        error=AIServiceNotConfiguredError()
    )

    response = client.post("/workflows/generate", json={"goal": "Build portfolio"})
    assert response.status_code == 503
    assert "Missing GEMINI_API_KEY" in response.json()["detail"]


def test_provider_failure_handling(client):
    """15. Return appropriate HTTP status codes for various provider failures."""
    # Rate limit (429)
    app.dependency_overrides[get_ai_generator] = lambda: FakeAIGenerator(
        error=AIRateLimitError()
    )
    r_rate = client.post("/workflows/generate", json={"goal": "Build portfolio"})
    assert r_rate.status_code == 429
    assert "rate limit exceeded" in r_rate.json()["detail"]

    # Timeout (504)
    app.dependency_overrides[get_ai_generator] = lambda: FakeAIGenerator(
        error=AITimeoutError()
    )
    r_timeout = client.post("/workflows/generate", json={"goal": "Build portfolio"})
    assert r_timeout.status_code == 504
    assert "timed out" in r_timeout.json()["detail"]

    # Provider error (502)
    app.dependency_overrides[get_ai_generator] = lambda: FakeAIGenerator(
        error=AIProviderError("Upstream service unavailable")
    )
    r_provider = client.post("/workflows/generate", json={"goal": "Build portfolio"})
    assert r_provider.status_code == 502

    # Parsing error (502)
    app.dependency_overrides[get_ai_generator] = lambda: FakeAIGenerator(
        error=AIParsingError()
    )
    r_parse = client.post("/workflows/generate", json={"goal": "Build portfolio"})
    assert r_parse.status_code == 502


# ============================================================================
# 5. Database Isolation and Persistence Safeguard Test
# ============================================================================

def test_generation_does_not_persist_to_database(client, valid_proposal, db_session):
    """16. Verify that generating a proposal does NOT write to workflows, tasks, or dependencies."""
    app.dependency_overrides[get_ai_generator] = lambda: FakeAIGenerator(proposal=valid_proposal)

    # Initial counts
    assert len(db_session.scalars(select(Workflow)).all()) == 0
    assert len(db_session.scalars(select(Task)).all()) == 0
    assert len(db_session.scalars(select(TaskDependency)).all()) == 0

    response = client.post(
        "/workflows/generate",
        json={"goal": "Build and deploy portfolio website"},
    )
    assert response.status_code == 200
    assert response.json()["is_persisted"] is False

    # Counts after generation must still be 0
    db_session.expire_all()
    assert len(db_session.scalars(select(Workflow)).all()) == 0
    assert len(db_session.scalars(select(Task)).all()) == 0
    assert len(db_session.scalars(select(TaskDependency)).all()) == 0
