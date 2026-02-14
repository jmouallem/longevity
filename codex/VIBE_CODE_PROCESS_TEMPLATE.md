# Vibe Coding Process Template
## A Structured Method for AI-Assisted Product Development

This document defines a disciplined, repeatable process for building software with AI coding agents while preventing drift, scope creep, and architectural inconsistency.

Keep this template generic across projects.

---

## Overview

Vibe coding is not "ask AI to build everything."

Vibe coding is a constraint-driven, slice-based workflow where AI accelerates delivery without replacing intent, architecture, or quality controls.

Process rule: move through planning layers before writing production code.

---

## Step 1 - Clarify Vision

Define:
- Problem statement
- Target users
- Desired outcomes
- Constraints (technical, legal, hosting, privacy)
- Explicit non-goals

Outputs:
- Vision statement
- Problem statement
- Constraints list

---

## Step 2 - Capture User Needs

Translate vision into concrete needs:
- Core capabilities
- Functional requirements
- Non-functional requirements
- Safety boundaries
- Data boundaries

Output:
- `USER_NEEDS.md`

Question answered: what must exist?

---

## Step 3 - Convert Needs to a Checklist

Turn each need into a binary, testable statement.

Output:
- `USER_NEEDS_CHECKLIST.md`

Checklist items should be:
- Observable
- Verifiable
- Implementable

This avoids vague "it works" conclusions.

---

## Step 4 - Define Architecture

Define:
- Runtime model
- Data model and storage
- API conventions
- Service boundaries
- Integration boundaries
- Security and privacy model
- Failure and recovery behavior

Output:
- `ARCHITECTURE.md`

Question answered: how is the system structured?

---

## Step 5 - Create Technical Blueprint

Define:
- Directory structure
- Core modules
- Initial schema
- Endpoint contracts
- Deployment model
- Environment variables
- Test strategy

Output:
- `BLUEPRINT.md`

Question answered: how will we implement it?

---

## Step 6 - Build Roadmap and Slices

Break delivery into phases, then into vertical slices.

Outputs:
- `BUILD_ROADMAP.md`
- `codex/slice_prompt_<n>.md` (one per slice)

Each slice must define:
- In-scope work
- Out-of-scope work
- Acceptance criteria
- Verification steps

Goal: tight diffs, deployable increments, controlled AI behavior.

---

## Step 7 - Add Agent Governance

Before coding, define:
- Agent behavior constraints
- Drift checks
- Definition of done
- Review gates

Outputs:
- `AGENTS.md`
- `codex/system_prompt.md`
- `DRIFT_DETECTION_CHECKLIST.md` (or equivalent section)

---

## Step 8 - Define Source of Truth Order

When docs conflict, resolve in this order:
1. `USER_NEEDS.md`
2. `USER_NEEDS_CHECKLIST.md`
3. `ARCHITECTURE.md`
4. `BLUEPRINT.md`
5. `BUILD_ROADMAP.md`
6. Active slice prompt (`codex/slice_prompt_X.md`)

This keeps implementation aligned to product intent.

---

## Step 9 - Implement One Slice at a Time

For each slice:
1. Confirm scope and acceptance criteria
2. Implement minimal viable diff
3. Run validations/tests
4. Perform drift check
5. Commit focused change set

Do not merge multiple slices into one change.

---

## Step 10 - Run Traceability and Alignment Reviews

At regular checkpoints, verify:
- Implemented behavior maps to checklist items
- Architecture still matches constraints
- No silent scope expansion
- Docs remain internally consistent

Traceability artifacts:
- Requirement-to-slice mapping
- Slice-to-files mapping
- Acceptance evidence per slice

If misalignment exists, either update docs intentionally or refactor code to match approved intent.

---

## Step 11 - Close the Feedback Loop

Run end-to-end walkthroughs and gather feedback:
- Onboarding flow
- Core outcomes
- Error paths
- Safety boundaries
- Performance basics
- Messaging clarity

Then update:
- User needs (if necessary)
- Architecture and blueprint
- Next slice priorities

This supports intentional evolution instead of reactive changes.

---

## Rules of Thumb

- Small slices over large rewrites
- Schema-first decisions
- Test early, test often
- Explicit non-goals
- Deterministic persistence and contracts
- AI as accelerator, not product owner
- Docs are living artifacts

---

## Ready-to-Build Checklist

Start implementation only when these are complete:
- Vision and constraints
- User needs
- Verifiable checklist
- Architecture
- Blueprint
- Roadmap and slices
- Agent governance
- Drift checks
- Baseline validation strategy

---

## Final Principle

Structure precedes acceleration.

Discipline protects intent.

Traceability keeps delivery honest.
