#!/usr/bin/env python3
"""CLI script to view skill usage logs.

Usage:
    poetry run python .agent/view_skill_logs.py [--stats] [--limit N]
"""

import argparse
import sys
from pathlib import Path

# Add script's directory (.agent/) to path to import skill_logger
sys.path.insert(0, str(Path(__file__).parent))

# Import directly from the same directory
from skill_logger import get_recent_skill_usage, get_skill_statistics


def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="View agent skill usage logs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show skill usage statistics instead of recent entries",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of recent entries to show (default: 20)",
    )

    args = parser.parse_args()

    if args.stats:
        stats = get_skill_statistics()
        print("Skill Usage Statistics")
        print("=" * 50)
        print(f"Total skill uses: {stats['total_uses']}")
        print(f"Unique skills used: {stats['unique_skills']}")
        print("\nUsage by skill:")
        for skill, count in sorted(
            stats["by_skill"].items(), key=lambda x: x[1], reverse=True
        ):
            print(f"  {skill}: {count}")
    else:
        entries = get_recent_skill_usage(limit=args.limit)
        if not entries:
            print("No skill usage logged yet.")
            return

        print(f"Recent Skill Usage (last {len(entries)} entries)")
        print("=" * 50)
        for entry in entries:
            timestamp = entry.get("timestamp", "unknown")
            skill = entry.get("skill", "unknown")
            context = entry.get("context", "")
            action = entry.get("action", "")

            print(f"\n[{timestamp}] {skill}")
            if context:
                print(f"  Context: {context}")
            if action:
                print(f"  Action: {action}")


if __name__ == "__main__":
    main()
