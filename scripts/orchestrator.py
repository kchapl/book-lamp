import os
import subprocess
import time


def run_swarm():
    if not os.path.exists("subagents.yaml"):
        print("❌ Error: No subagents.yaml found. Run planner.py first.")
        return

    print("🚀 Orchestrator: Launching agent swarm...")

    # In a real Antigravity environment, this would call the internal
    # 'gemini-cli' to spawn autonomous agents.
    processes = []

    # Simulating the dispatch of 3 agents
    agents = ["Architect", "Coder", "Tester"]
    for agent in agents:
        # Commands use the Antigravity shim to ensure project style is enforced
        cmd = f"gemini-cli 'Act as {agent} and follow the task_plan.md. Adhere to Python/TypeScript conventions in GEMINI.md.'"
        p = subprocess.Popen(cmd, shell=True)
        processes.append(p)
        print(f"  -> {agent} agent dispatched.")

    # Monitor progress
    while any(p.poll() is None for p in processes):
        time.sleep(2)
        # The IDE UI monitors progress.md automatically
        with open("progress.md", "a") as log:
            log.write(
                f"[{time.strftime('%H:%M:%S')}] Swarm active... processing tasks.\n"
            )

    print("✅ Orchestrator: All agents have returned. Mission complete.")


if __name__ == "__main__":
    run_swarm()
