import pytest

from app.services.scheduler import calculate_schedule


def test_schedule_with_dependencies_and_parallel_tasks():
    tasks = [
        {
            "id": 1,
            "title": "Design database",
            "estimated_hours": 2,
            "depends_on": [],
        },
        {
            "id": 2,
            "title": "Build backend",
            "estimated_hours": 5,
            "depends_on": [1],
        },
        {
            "id": 3,
            "title": "Build frontend",
            "estimated_hours": 6,
            "depends_on": [1],
        },
        {
            "id": 4,
            "title": "Integrate application",
            "estimated_hours": 3,
            "depends_on": [2, 3],
        },
    ]

    result = calculate_schedule(tasks)

    schedule = {
        item["task_id"]: item
        for item in result["schedule"]
    }

    assert schedule[1]["earliest_start_hour"] == 0
    assert schedule[1]["earliest_finish_hour"] == 2

    assert schedule[2]["earliest_start_hour"] == 2
    assert schedule[2]["earliest_finish_hour"] == 7

    assert schedule[3]["earliest_start_hour"] == 2
    assert schedule[3]["earliest_finish_hour"] == 8

    assert schedule[4]["earliest_start_hour"] == 8
    assert schedule[4]["earliest_finish_hour"] == 11

    assert result["total_duration_hours"] == 11


def test_scheduler_rejects_cycles():
    tasks = [
        {
            "id": 1,
            "title": "Task A",
            "estimated_hours": 2,
            "depends_on": [2],
        },
        {
            "id": 2,
            "title": "Task B",
            "estimated_hours": 3,
            "depends_on": [1],
        },
    ]

    with pytest.raises(ValueError, match="cycle"):
        calculate_schedule(tasks)


def test_scheduler_rejects_unknown_dependency():
    tasks = [
        {
            "id": 1,
            "title": "Task A",
            "estimated_hours": 2,
            "depends_on": [99],
        }
    ]

    with pytest.raises(ValueError, match="unknown task"):
        calculate_schedule(tasks)