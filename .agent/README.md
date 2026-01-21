# Agent Skills Directory

This directory contains skills that guide the AI agent's behaviour when working on the Book Lamp project.

## Skills

- **librarian**: Expertise in bibliographic data, book classification, citation formats, and library science principles
- **book-lamp-development**: Guidelines for developing, maintaining, and extending the Book Lamp application
- **python-tutor**: Guidance on Python code structure, organisation, and architectural patterns
- **web-designer**: Guidance on creating beautiful, accessible, and user-friendly web pages

## Skill Usage Logging

The agent can log when it uses skills to help track which skills are most relevant to different tasks.

### How It Works

When the agent uses a skill, it can call the logging function to record:
- Which skill was used
- The context (why the skill was relevant)
- The action taken (what was done with the skill)

### Viewing Skill Usage

To see recent skill usage:

```bash
# View recent entries (last 20, default)
poetry run python .agent/view_skill_logs.py

# View more entries
poetry run python .agent/view_skill_logs.py --limit 50

# View statistics
poetry run python .agent/view_skill_logs.py --stats

# Or view the raw log file
tail -20 .agent/skill_usage.log
```

### Log Files

- `skill_usage.log`: Human-readable log file with timestamped entries
- `skill_usage.json`: Structured JSON log for programmatic access

Both files are automatically created when skills are logged and are kept in this directory. These files are gitignored and won't be committed to version control.

### Example Usage in Code

The agent can log skill usage like this:

```python
from .agent.skill_logger import log_skill_usage

# When using the librarian skill
log_skill_usage(
    skill_name="librarian",
    context="Validating ISBN format and bibliographic data",
    action="Checking ISBN-13 checksum and normalising book metadata"
)

# When using the book-lamp-development skill
log_skill_usage(
    skill_name="book-lamp-development",
    context="Following project architecture patterns",
    action="Isolating Google Sheets API calls in adapter layer"
)
```
