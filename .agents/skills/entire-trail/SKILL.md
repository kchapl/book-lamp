---
name: entire-trail
description: Inspect Entire trail findings, review timelines, and eval statuses for the current repository branch, verify each finding against local code, and propose fixes. Use when asked to check Entire trails, review trail findings, or debug trail evals.
---

# Entire Trail Review

Inspect and act on **Entire** (`entire.com`) trail findings for the active repository without requiring hardcoded paths.

## Workflow

1. Run `entire agent-help` if unsure of subcommand flags.
2. Run `entire trail show --json` (and `entire trail timeline --json` if needed) to inspect the current branch's trail, eval scores, and findings.
3. Verify each finding against the local codebase before proposing fixes.
