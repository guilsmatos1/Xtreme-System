---
name: devops--skill-organizer
description: Run skill-organizer operations to synchronize, check status, and manage organized skill trees in the project.
metadata:
    skill-organizer:
        original-name: skill-organizer
        source-relative-path: devops/skill-organizer
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Skill Organizer Management

This skill allows the agent to run `skill-organizer` operations to synchronize, verify status, and manage project-local skill symlinks.

## Quick Start

### 1. Check Status
Verify the status of the local skill layout and check if there are any drifted, missing, or broken symlinks:
```bash
skill-organizer status
```

### 2. Synchronize Skills
Synchronize the organized source skill tree under `skills-organized/` into the flat target folder `.agents/skills` (and any linked folders like `.claude/skills`):
```bash
skill-organizer sync
```

## Setup & Configuration

The local configuration file `.skill-organizer.yml` is located in the project root:
```yaml
source: /Users/guilsmatos/orca/projects/xtreme-system/skills-organized
target: /Users/guilsmatos/orca/projects/xtreme-system/.agents/skills
```

When run in the project root, `skill-organizer` automatically loads this configuration.
