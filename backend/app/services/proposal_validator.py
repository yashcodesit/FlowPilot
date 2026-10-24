import networkx as nx

from app.schemas.generation import WorkflowProposal


class ProposalValidationError(ValueError):
    """Raised when a generated workflow proposal fails structural or relational validation."""
    pass


def validate_proposal(proposal: WorkflowProposal) -> WorkflowProposal:
    """
    Validate the structural and relational integrity of a workflow proposal.

    Checks:
    1. Task count is within allowable limits (1 to 30 tasks).
    2. Every task reference (e.g. 'T1', 'T2') is unique.
    3. Every dependency reference exists in the proposal.
    4. A task cannot depend on itself.
    5. Deduplicates redundant dependency references.
    6. Ensures the dependency graph is a Directed Acyclic Graph (DAG) with no cycles.
    7. Validates that all durations are positive numbers.
    8. Validates that task titles are non-empty.
    """
    if not proposal.tasks:
        raise ProposalValidationError("Proposal must contain at least one task.")

    if len(proposal.tasks) > 30:
        raise ProposalValidationError(
            f"Proposal contains too many tasks ({len(proposal.tasks)}). Maximum allowed is 30."
        )

    # 1. Check for unique task references
    seen_refs = set()
    ref_map = {}

    for task in proposal.tasks:
        clean_ref = task.ref.strip()
        if not clean_ref:
            raise ProposalValidationError("Task reference cannot be empty.")

        if clean_ref in seen_refs:
            raise ProposalValidationError(
                f"Duplicate task reference detected in proposal: '{clean_ref}'."
            )

        seen_refs.add(clean_ref)
        ref_map[clean_ref] = task
        task.ref = clean_ref

    # 2. Build graph and check dependencies
    graph = nx.DiGraph()
    graph.add_nodes_from(seen_refs)

    for task in proposal.tasks:
        # Validate task duration
        if task.estimated_hours is None or task.estimated_hours <= 0:
            raise ProposalValidationError(
                f"Task '{task.ref}' must have a positive estimated duration."
            )

        # Validate task title
        if not task.title or not task.title.strip():
            raise ProposalValidationError(
                f"Task '{task.ref}' title cannot be empty or whitespace-only."
            )

        # Normalize and validate dependencies
        normalized_deps: list[str] = []
        for dep in task.depends_on:
            clean_dep = dep.strip()
            if not clean_dep:
                continue

            if clean_dep not in seen_refs:
                raise ProposalValidationError(
                    f"Task '{task.ref}' depends on unknown task reference '{clean_dep}'."
                )

            if clean_dep == task.ref:
                raise ProposalValidationError(
                    f"Task '{task.ref}' cannot depend on itself."
                )

            if clean_dep not in normalized_deps:
                normalized_deps.append(clean_dep)

            # Prerequisite executes before this task
            graph.add_edge(clean_dep, task.ref)

        task.depends_on = normalized_deps

    # 3. Check for cycles using NetworkX
    try:
        cycle = nx.find_cycle(graph, orientation="original")
        cycle_str = " -> ".join(f"{u} to {v}" for u, v, _ in cycle)
        raise ProposalValidationError(
            f"Dependency cycle detected in generated proposal: {cycle_str}."
        )
    except nx.NetworkXNoCycle:
        pass

    return proposal
