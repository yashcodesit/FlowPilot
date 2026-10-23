import pytest
from app.models.task import Task
from app.models.workflow import Workflow


# ============================================================================
# Task Status Tests (Feature A)
# ============================================================================

def test_update_status_pending_to_in_progress(client, sample_workflow, sample_task, db_session):
    """1. Successfully update a task from pending to in_progress."""
    response = client.patch(
        f"/workflows/{sample_workflow.id}/tasks/{sample_task.id}/status",
        json={"status": "in_progress"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_task.id
    assert data["status"] == "in_progress"

    # Verify database persistence
    db_session.expire_all()
    persisted = db_session.get(Task, sample_task.id)
    assert persisted.status == "in_progress"


def test_update_status_to_completed(client, sample_workflow, sample_task, db_session):
    """2. Successfully update a task to completed."""
    response = client.patch(
        f"/workflows/{sample_workflow.id}/tasks/{sample_task.id}/status",
        json={"status": "completed"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"

    db_session.expire_all()
    persisted = db_session.get(Task, sample_task.id)
    assert persisted.status == "completed"


def test_update_status_to_blocked(client, sample_workflow, sample_task, db_session):
    """Test updating task status to blocked."""
    response = client.patch(
        f"/workflows/{sample_workflow.id}/tasks/{sample_task.id}/status",
        json={"status": "blocked"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"

    db_session.expire_all()
    persisted = db_session.get(Task, sample_task.id)
    assert persisted.status == "blocked"


def test_update_status_rejects_unsupported_status(client, sample_workflow, sample_task):
    """3. Reject an unsupported status with 422 Unprocessable Entity."""
    response = client.patch(
        f"/workflows/{sample_workflow.id}/tasks/{sample_task.id}/status",
        json={"status": "unknown_status"},
    )

    assert response.status_code == 422


def test_update_status_nonexistent_workflow(client, sample_task):
    """4. Return 404 for a nonexistent workflow."""
    nonexistent_workflow_id = 99999
    response = client.patch(
        f"/workflows/{nonexistent_workflow_id}/tasks/{sample_task.id}/status",
        json={"status": "in_progress"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workflow not found."


def test_update_status_nonexistent_task(client, sample_workflow):
    """5. Return 404 for a nonexistent task."""
    nonexistent_task_id = 99999
    response = client.patch(
        f"/workflows/{sample_workflow.id}/tasks/{nonexistent_task_id}/status",
        json={"status": "in_progress"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found."


def test_update_status_wrong_workflow_id(client, sample_task, db_session):
    """6. Reject updating a task through the wrong workflow ID."""
    other_workflow = Workflow(
        title="Other Workflow",
        status="draft",
    )
    db_session.add(other_workflow)
    db_session.commit()
    db_session.refresh(other_workflow)

    response = client.patch(
        f"/workflows/{other_workflow.id}/tasks/{sample_task.id}/status",
        json={"status": "in_progress"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found in this workflow."


def test_status_remains_unchanged_after_invalid_update(client, sample_workflow, sample_task, db_session):
    """7. Verify that the status remains unchanged after an invalid update."""
    original_status = sample_task.status
    assert original_status == "pending"

    # Attempt invalid status update
    response = client.patch(
        f"/workflows/{sample_workflow.id}/tasks/{sample_task.id}/status",
        json={"status": "invalid_status_xyz"},
    )
    assert response.status_code == 422

    # Verify status in database remains pending
    db_session.expire_all()
    persisted = db_session.get(Task, sample_task.id)
    assert persisted.status == original_status


# ============================================================================
# Task Validation and Update Tests (Features B and C)
# ============================================================================

def test_create_task_rejects_whitespace_title(client, sample_workflow):
    """8. Reject a title consisting only of whitespace on task creation."""
    response = client.post(
        f"/workflows/{sample_workflow.id}/tasks",
        json={
            "title": "    ",
            "priority": "medium",
        },
    )

    assert response.status_code == 422


def test_update_task_rejects_whitespace_title(client, sample_workflow, sample_task):
    """8b. Reject a title consisting only of whitespace on task update."""
    response = client.patch(
        f"/workflows/{sample_workflow.id}/tasks/{sample_task.id}",
        json={"title": "   \t  \n  "},
    )

    assert response.status_code == 422


def test_create_task_rejects_non_positive_estimated_hours(client, sample_workflow):
    """9. Reject zero or negative estimated duration on creation."""
    # Zero
    res_zero = client.post(
        f"/workflows/{sample_workflow.id}/tasks",
        json={"title": "Test Task", "estimated_hours": 0},
    )
    assert res_zero.status_code == 422

    # Negative
    res_neg = client.post(
        f"/workflows/{sample_workflow.id}/tasks",
        json={"title": "Test Task", "estimated_hours": -2.5},
    )
    assert res_neg.status_code == 422


def test_update_task_rejects_non_positive_estimated_hours(client, sample_workflow, sample_task):
    """9b. Reject zero or negative estimated duration on update."""
    # Zero
    res_zero = client.patch(
        f"/workflows/{sample_workflow.id}/tasks/{sample_task.id}",
        json={"estimated_hours": 0},
    )
    assert res_zero.status_code == 422

    # Negative
    res_neg = client.patch(
        f"/workflows/{sample_workflow.id}/tasks/{sample_task.id}",
        json={"estimated_hours": -1.0},
    )
    assert res_neg.status_code == 422


def test_create_task_rejects_unsupported_priority(client, sample_workflow):
    """10. Reject an unsupported priority on creation."""
    response = client.post(
        f"/workflows/{sample_workflow.id}/tasks",
        json={"title": "Test Task", "priority": "super_critical"},
    )
    assert response.status_code == 422


def test_update_task_rejects_unsupported_priority(client, sample_workflow, sample_task):
    """10b. Reject an unsupported priority on update."""
    response = client.patch(
        f"/workflows/{sample_workflow.id}/tasks/{sample_task.id}",
        json={"priority": "invalid_priority"},
    )
    assert response.status_code == 422


def test_update_one_field_preserves_unrelated_fields(client, sample_workflow, sample_task, db_session):
    """11. Successfully update one field without overwriting unrelated fields."""
    original_description = sample_task.description
    original_priority = sample_task.priority
    original_estimated_hours = sample_task.estimated_hours
    original_status = sample_task.status

    # Update only the title
    response = client.patch(
        f"/workflows/{sample_workflow.id}/tasks/{sample_task.id}",
        json={"title": "Updated Title Only"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title Only"
    assert data["description"] == original_description
    assert data["priority"] == original_priority
    assert data["estimated_hours"] == original_estimated_hours
    assert data["status"] == original_status

    # 12. Verify that the database reflects a successful update
    db_session.expire_all()
    persisted = db_session.get(Task, sample_task.id)
    assert persisted.title == "Updated Title Only"
    assert persisted.description == original_description
    assert persisted.priority == original_priority
    assert persisted.estimated_hours == original_estimated_hours
    assert persisted.status == original_status


def test_update_task_rejects_null_on_non_nullable_fields(client, sample_workflow, sample_task):
    """Reject explicit null values for non-nullable fields (title, priority, status)."""
    # Title null
    res_title = client.patch(
        f"/workflows/{sample_workflow.id}/tasks/{sample_task.id}",
        json={"title": None},
    )
    assert res_title.status_code == 422

    # Priority null
    res_priority = client.patch(
        f"/workflows/{sample_workflow.id}/tasks/{sample_task.id}",
        json={"priority": None},
    )
    assert res_priority.status_code == 422

    # Status null on status endpoint
    res_status = client.patch(
        f"/workflows/{sample_workflow.id}/tasks/{sample_task.id}/status",
        json={"status": None},
    )
    assert res_status.status_code == 422


def test_update_task_allows_null_on_nullable_fields(client, sample_workflow, sample_task, db_session):
    """Allow explicitly resetting nullable fields (description, estimated_hours) to null."""
    response = client.patch(
        f"/workflows/{sample_workflow.id}/tasks/{sample_task.id}",
        json={"description": None, "estimated_hours": None},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["description"] is None
    assert data["estimated_hours"] is None

    db_session.expire_all()
    persisted = db_session.get(Task, sample_task.id)
    assert persisted.description is None
    assert persisted.estimated_hours is None


def test_get_task_details_success(client, sample_workflow, sample_task):
    """Retrieve task details if it belongs to the workflow."""
    response = client.get(f"/workflows/{sample_workflow.id}/tasks/{sample_task.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_task.id
    assert data["workflow_id"] == sample_workflow.id
    assert data["title"] == sample_task.title
    assert data["status"] == sample_task.status
    assert data["priority"] == sample_task.priority


def test_get_task_details_wrong_workflow(client, sample_task, db_session):
    """Return 404 when getting task details through wrong workflow ID."""
    other_workflow = Workflow(title="Other Workflow", status="draft")
    db_session.add(other_workflow)
    db_session.commit()
    db_session.refresh(other_workflow)

    response = client.get(f"/workflows/{other_workflow.id}/tasks/{sample_task.id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found in this workflow."


def test_get_task_details_nonexistent_workflow(client, sample_task):
    """Return 404 when getting task details for nonexistent workflow."""
    response = client.get(f"/workflows/99999/tasks/{sample_task.id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Workflow not found."


def test_get_task_details_nonexistent_task(client, sample_workflow):
    """Return 404 when getting task details for nonexistent task."""
    response = client.get(f"/workflows/{sample_workflow.id}/tasks/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found in this workflow."
