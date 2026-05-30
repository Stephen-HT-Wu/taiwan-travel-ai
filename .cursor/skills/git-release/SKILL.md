---
name: git-release
description: Git commit and push workflow for taiwan-travel-ai. Use when the user asks to commit, push, or prepare changes for GitHub.
---

# Git Release

## Before commit

1. `git status` — confirm `.env` is **not** staged
2. `git diff` — review changes
3. Never commit secrets (`ANTHROPIC_API_KEY`, `TDX_*`, `CWA_*`, `GEMINI_*`)

## Commit message

1–2 sentences, focus on **why**:

```
Improve chat UX with progress tracking and fix TDX bus API.

Add streaming status panels and correct bus route field selection.
```

Use HEREDOC for multi-line messages.

## Push

```bash
git push origin master
```

Remote: `git@github.com:Stephen-HT-Wu/taiwan-travel-ai.git`

Collaborator account `Stephen-Wu-TVBS` may need repo access if push denied.

## Do not

- `git push --force` to main without explicit user request
- `git commit --amend` unless user asked and commit not pushed
- Update git config
