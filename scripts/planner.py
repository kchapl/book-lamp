import sys

import yaml


def create_plan(mission_goal):
    # Define the specialized roles for the swarm
    plan = {
        "mission": mission_goal,
        "agents": [
            {
                "role": "Architect",
                "task": "Design system structure following Python/TypeScript conventions in GEMINI.md.",
            },
            {
                "role": "Coder",
                "task": "Implement logic using Python for backend and TypeScript for frontend.",
            },
            {
                "role": "Tester",
                "task": "Write Pytest unit tests for backend and Vitest for frontend components.",
            },
        ],
    }

    # Generate the required Manus state files
    with open("subagents.yaml", "w") as f:
        yaml.dump(plan, f)

    with open("task_plan.md", "w") as f:
        f.write(
            f"# Mission: {mission_goal}\n\n- [ ] Initialize project structure\n- [ ] Implement core logic\n- [ ] Run verification tests"
        )

    with open("findings.md", "w") as f:
        f.write("# Shared Research & Discoveries\n")

    print(f"✅ Planner: Created mission for '{mission_goal}'")


if __name__ == "__main__":
    goal = sys.argv[1] if len(sys.argv) > 1 else "New Mission"
    create_plan(goal)
