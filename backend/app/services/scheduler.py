from collections import defaultdict

import networkx as nx


def calculate_schedule(tasks: list[dict]) -> dict:
    """
    Calculate an earliest-start schedule for a workflow.

    Each task must contain:
        id: int
        title: str
        estimated_hours: float

    Optional:
        depends_on: list[int]

    Dependencies refer to prerequisite task IDs.
    """

    if not tasks:
        return {
            "schedule": [],
            "total_duration_hours": 0,
        }

    task_by_id = {task["id"]: task for task in tasks}

    if len(task_by_id) != len(tasks):
        raise ValueError("Task IDs must be unique.")

    graph = nx.DiGraph()
    graph.add_nodes_from(task_by_id)

    for task in tasks:
        duration = task.get("estimated_hours")

        if duration is None or duration < 0:
            raise ValueError(
                f"Task {task['id']} must have a non-negative duration."
            )

        for prerequisite_id in task.get("depends_on", []):
            if prerequisite_id not in task_by_id:
                raise ValueError(
                    f"Task {task['id']} depends on unknown task "
                    f"{prerequisite_id}."
                )

            if prerequisite_id == task["id"]:
                raise ValueError(
                    f"Task {task['id']} cannot depend on itself."
                )

            # The prerequisite must execute before this task.
            graph.add_edge(prerequisite_id, task["id"])

    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError(
            "Cannot schedule this workflow because its dependencies "
            "contain a cycle."
        )

    earliest_start = defaultdict(float)
    earliest_finish = {}

    schedule = []

    for task_id in nx.topological_sort(graph):
        task = task_by_id[task_id]
        duration = task["estimated_hours"]

        prerequisite_ids = list(graph.predecessors(task_id))

        start = max(
            (earliest_finish[pid] for pid in prerequisite_ids),
            default=0,
        )

        finish = start + duration

        earliest_start[task_id] = start
        earliest_finish[task_id] = finish

        schedule.append({
            "task_id": task_id,
            "title": task["title"],
            "depends_on": prerequisite_ids,
            "estimated_hours": duration,
            "earliest_start_hour": start,
            "earliest_finish_hour": finish,
        })

    return {
        "schedule": schedule,
        "total_duration_hours": max(earliest_finish.values()),
    }