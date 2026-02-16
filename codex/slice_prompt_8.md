# Slice 8 - Daily Log + Overall Summary + Chat History + Mobile-App UI

## Objective
Implement the next user-facing product layer so the app behaves like a mobile-first coaching app, not a static web page:
- add a structured daily log workflow,
- add an overall summary view (today / 7-day / 30-day),
- persist and render chat history,
- prepare multimodal input foundations (voice + image),
- move UI shell to phone-app style navigation and layout.

## In Scope

### 1) Daily Log
- Add a structured daily check-in data model and API.
- Capture at minimum:
  - sleep_hours
  - energy (1-10)
  - mood (1-10)
  - stress (1-10)
  - activity/training indicator
  - nutrition adherence indicator
  - free-text notes (bounded length)
- Allow create/update for same user/date (idempotent upsert behavior).
- Expose recent log list endpoint for UI rendering.

### 2) Overall Summary
- Add a summary endpoint that returns:
  - today snapshot
  - 7-day trend summary
  - 30-day trend summary
  - top wins
  - top risks / watch items
  - one next best action
- Summary must be deterministic and available without requiring live LLM call.
- If LLM augmentation is used, require safe fallback path.

### 3) Chat History
- Persist full chat turns (user message + assistant response) with timestamps.
- Group turns into conversation threads per user.
- Add endpoints to:
  - list threads
  - list messages for a thread
  - create new thread
- Default chat can continue in current thread; user can start a new thread.

### 4) Multimodal Foundations (Slice 8 scope boundary)
- Add API contracts and stubs for:
  - voice input submission (transcript-first contract)
  - image input submission (structured extraction contract)
- Enforce policy:
  - do not persist raw audio files
  - do not persist raw images
  - persist only transcript / structured extracted outputs
- Basic stub responses acceptable in this slice; full model integrations can be follow-on.

### 5) Mobile-App Style UI Shell
- Rework workspace UI into phone-app style:
  - mobile-first viewport layout
  - app shell with top bar + bottom nav
  - chat-first home tab
  - separate tabs/views for Summary, Daily Log, History, Settings
- Keep desktop functional/responsive, but prioritize mobile composition.
- Preserve existing auth/session behavior.

## Out Of Scope
- Full native mobile app packaging.
- Real-time streaming responses.
- Full multimodal model quality optimization.
- External connector sync (Apple Health/Hume live integration).
- Broad redesign of onboarding flow unless needed for nav consistency.

## API Contracts (Target)

### Daily Log
- `PUT /daily-log/{date}` (upsert for authenticated user)
- `GET /daily-log?from=YYYY-MM-DD&to=YYYY-MM-DD`

### Summary
- `GET /summary/overall`

### Chat History
- `GET /chat/threads`
- `POST /chat/threads`
- `GET /chat/threads/{thread_id}/messages`
- `POST /chat/threads/{thread_id}/messages` (optional if reusing existing coach endpoint internally)

### Multimodal Stubs
- `POST /coach/voice` (accept transcript payload in Slice 8)
- `POST /coach/meal-photo` (accept structured placeholder metadata in Slice 8)

## Data Model Additions (Target)
- `daily_logs`
  - user_id, log_date (unique per user/date), sleep_hours, energy, mood, stress, training_flag, nutrition_flag, notes, created_at, updated_at
- `chat_threads`
  - id, user_id, title, created_at, updated_at
- `chat_messages`
  - id, thread_id, user_id, role (user/assistant/system), message_text, created_at

## Safety and Privacy Constraints
- Auth required on all new user-scoped endpoints.
- Strict per-user isolation for all reads/writes.
- No raw image/audio storage.
- Keep non-medical disclaimer behavior in coaching outputs.

## Acceptance Criteria
- User can submit and edit daily log entries for a date.
- User can view recent daily logs in UI.
- Overall summary endpoint returns stable shape with today/7-day/30-day sections.
- Chat messages are persisted and visible in history view.
- User can switch threads and continue chat context.
- Mobile-first app shell is active with phone-style layout and bottom navigation.
- Voice/image endpoints exist with policy-safe storage behavior (no raw media persistence).
- Existing auth + coaching + intake flows still work.
- Tests pass.

## Testing Requirements
- API tests for daily log upsert/list and per-user isolation.
- API tests for summary response contract.
- API tests for thread/message isolation and ordering.
- UI smoke test coverage for tab navigation and history rendering.
- No-network tests by default for multimodal stubs and summary fallback.

## Files Allowed to Change
- `app/api/*` (new route modules allowed)
- `app/db/models.py`
- `app/db/session.py` (if schema init updates are needed)
- `app/core/*` (summary + aggregation logic)
- `app/services/*` (history/multimodal helpers)
- `app/static/app.html`
- `tests/api/*`
- `tests/unit/*`
- `docs/*` and `PROJECT_CONTEXT.md` for consistency updates

## Notes
- Keep diffs focused and incremental.
- Prefer deterministic summary math/aggregation before heavier LLM summarization.
- Optimize for usability and low-friction daily engagement.
