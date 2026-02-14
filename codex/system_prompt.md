# System Prompt Index

## Purpose
This file is an index to avoid duplicated prompt content and reduce drift.

## Single Source Of Truth
The canonical slice instructions live in:
- `codex/slice_prompt_1.md`
- `codex/slice_prompt_2.md`
- `codex/slice_prompt_3.md`
- `codex/slice_prompt_4.md`
- `codex/slice_prompt_5.md`
- `codex/slice_prompt_6.md`

## Load Order
Use this load order to keep context tight and deterministic:
1. `AGENTS.md`
2. Active `codex/slice_prompt_<n>.md`
3. Only the minimum supporting docs needed from `docs/*` and `PROJECT_CONTEXT.md`

## Global Instructions
- Follow `AGENTS.md` for project-level constraints and quality bar.
- Work within one active slice unless user explicitly asks for multi-slice changes.

## Conflict Resolution
If instructions conflict, apply precedence in this order:
1. Active `codex/slice_prompt_<n>.md`
2. `AGENTS.md`
3. Reference docs (`docs/*`, `PROJECT_CONTEXT.md`, this index)

## Usage
- For slice-specific implementation, load only the relevant `slice_prompt_<n>.md`.
- Do not duplicate full slice bodies in this file.
- If a slice changes, update only that slice file.

## Maintenance Rule
When adding a new slice:
1. Create `codex/slice_prompt_<n>.md` using the existing slice files as structure guidance.
2. Add the new file path to this index.
3. Keep this file short; it should remain an index, not a merged prompt document.
