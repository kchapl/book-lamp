# Antigravity Swarm Skill

**Description:** Use this skill to coordinate multiple autonomous sub-agents for complex missions, parallel tasks, or full-stack feature implementation.

## Goal
To decompose high-level user requirements into parallelizable sub-tasks and execute them using a specialized team of agents.

## Instructions
1. **Planning Phase:** When a "mission" is requested, first invoke `scripts/planner.py` to generate a `subagents.yaml` and a `task_plan.md`.
2. **Team Assembly:** Deploy specialized agents based on the task (e.g., `coder-agent`, `test-agent`, `refactor-agent`).
3. **Communication:** All agents must share state via `findings.md` and `progress.md`.

## Tools
- `dispatch_subagent(task: string)`: Spawns a single worker for a specific file or bug.
- `run_mission(goal: string)`: Executes the full multi-agent orchestration.

## Constraints
- Do not execute the mission until the user approves the `task_plan.md` in the Manager View.
- Never exceed 5 concurrent sub-agents to avoid context drift.
