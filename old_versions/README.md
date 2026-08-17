# TIC Claude Code Setup

This package contains:

- `CLAUDE.md`: persistent repository instructions for Claude Code.
- `prompts/01_inspect_only.md`: inspect the repository without modifying it.
- `prompts/02_propose_reorganization.md`: create a professional reorganization plan.
- `prompts/03_implement_approved_plan.md`: implement only explicitly approved changes.
- `prompts/04_document_artifact.md`: prepare reviewer-facing documentation.
- `prompts/05_final_audit.md`: audit the organized artifact.
- `prompts/06_commit_and_release_prep.md`: prepare clean commits and release materials.

## Installation

From the root of the local `pic-compression` or TIC artifact repository:

```bash
cp /path/to/tic_claude_setup/CLAUDE.md .
mkdir -p prompts
cp /path/to/tic_claude_setup/prompts/*.md prompts/
```

Commit `CLAUDE.md` and the reusable prompts if they are intended to be shared with collaborators. Otherwise, keep personal prompts outside the repository.

## Recommended execution sequence

Start Claude Code from the repository root:

```bash
cd /path/to/tic-artifact
claude
```

Then submit the prompt contents in this order:

1. `prompts/01_inspect_only.md`
2. Review `docs/repository-inspection.md`.
3. `prompts/02_propose_reorganization.md`
4. Review and explicitly approve selected actions.
5. `prompts/03_implement_approved_plan.md`
6. `prompts/04_document_artifact.md`
7. `prompts/05_final_audit.md`
8. `prompts/06_commit_and_release_prep.md`

Do not run Prompt 3 until the reorganization plan has been reviewed and approved.

Claude Code automatically loads project-level `CLAUDE.md` instructions. Use `/memory` within Claude Code to inspect loaded instruction files.
