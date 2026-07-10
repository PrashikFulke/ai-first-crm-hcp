# AI-First CRM — HCP Interaction Logger

## Overview

This project implements the "Log Interaction Screen" of a pharmaceutical field-rep CRM using a dual-entry model: a structured form panel on the left and a conversational AI chat panel on the right share a single Redux store, so typing natural-language notes into the chat automatically drafts the structured form fields in real time. The AI layer is a stateful LangGraph agent that orchestrates six tools — two LLM-based and four database-backed — over a looping graph before streaming results back to the frontend via Server-Sent Events. Form submission is a separate, explicit human-triggered action that writes the drafted data to a Supabase PostgreSQL database in a single atomic transaction.

---

## Tech Stack

| Layer | Technology | Version / Model |
|---|---|---|
| API Server | FastAPI | 0.111.0 |
| ASGI Server | Uvicorn | 0.30.1 |
| Database ORM | SQLAlchemy | 2.0.30 |
| Database Driver | psycopg2-binary | 2.9.9 |
| Data Validation | Pydantic | 2.7.3 |
| Database Host | Supabase (PostgreSQL) | — |
| Agent Orchestration | LangGraph | (unpinned) |
| LLM Provider | Groq API via langchain-groq | (unpinned) |
| Extraction Model | `llama-3.1-8b-instant` | temperature=0 |
| Patch/Edit Model | `llama-3.1-8b-instant` | temperature=0 |
| Follow-up Model | `llama-3.3-70b-versatile` | temperature=0.7 |
| Orchestrator Model | `llama-3.1-8b-instant` | temperature=0 |
| Frontend Framework | React | ^19.2.7 |
| State Management | Redux Toolkit | ^2.12.0 |
| React-Redux Binding | react-redux | ^9.3.0 |
| Build Tool | Vite | ^8.1.1 |

---

## Architecture & Data Flow

### LangGraph Orchestration

The agent is a compiled `StateGraph` with three nodes and a conditional loop:

```
START → intent_router ──(tool_calls present)──→ tool_executor → intent_router (loop)
                      ──(no tool_calls)──────→ state_synchronizer → END
```

**`intent_router`** (`graph.py:35–62`): On every invocation, it strips all prior `SystemMessage` objects from the accumulated message list and re-injects two fresh system messages — the routing rules prompt and a grounding prompt containing the current form state serialised as JSON. It then calls `llm_with_tools.invoke()` on the updated message list. The LLM either returns `tool_calls` (triggering the executor) or a plain `AIMessage` (triggering the synchronizer).

**`tool_executor`** (`graph.py:136`): LangGraph's prebuilt `ToolNode`. Executes whatever tools the LLM requested, appends `ToolMessage` objects to the state, and routes back to `intent_router`. This loop allows the agent to call multiple tools across turns — e.g. extract, then resolve IDs, then suggest follow-ups — reading each result before deciding the next action.

**`state_synchronizer`** (`graph.py:77–128`): A pure-Python node with no LLM call. Scans backwards through the message list to the most recent `HumanMessage` boundary, parses every `ToolMessage` JSON in that window, and applies tool-specific merge logic:
- `edit_interaction` results: extracts the `updates` dict and merges each key into `pending_updates`.
- `draft_existing_interaction` results: flattens the entire `draft` dict into `pending_updates` (full record replacement).
- All other tools: applies the null/placeholder filter (`v is not None and v != "" and v != [] and v != "HCP"`) and excludes informational keys (`history`, `follow_ups`, `resolved`) from form state.

After merging, it checks mandatory fields (`hcp_name`, `topics_discussed`) and populates `validation_errors`. The final `form_state`, `pending_updates`, and `validation_errors` are returned to the graph and streamed to the frontend.

### Tool Registry

All six tools are bound to the orchestrator LLM via `llm.bind_tools(tools)` in `graph.py:13`.

| Tool Name | LLM Model | Description |
|---|---|---|
| `extract_interaction` | `llama-3.1-8b-instant` | Parses raw free-text rep notes into `InteractionExtraction` schema fields (`hcp_name`, `topics_discussed`, `sentiment`, `materials_shared`, `samples_distributed`) using `with_structured_output`. System prompt enforces strict grounding and field-boundary rules. |
| `edit_interaction` | `llama-3.1-8b-instant` | Receives the correction text and the serialised current form state. Uses `PATCH_SYSTEM_PROMPT` with few-shot examples to produce a minimal `EditInteractionSchema` patch (`Dict[str, Any]`) containing only explicitly requested changes. |
| `search_hcp_history` | None (pure DB) | Case-insensitive `ilike` query on `hcps.name`. Returns the 3 most recent `Interaction` records per matching HCP, ordered by `interaction_date DESC`. |
| `suggest_followups` | `llama-3.3-70b-versatile` | Generates exactly 3 strategic, life-science-specific follow-up actions via `FollowUpSuggestions` structured output. Uses the 70b model at temperature 0.7 — the only non-deterministic call in the system. |
| `resolve_materials_and_samples` | None (pure DB) | Accepts a `List[str]` of item names. For each, runs a separate `ilike` query against both `materials` and `samples` tables. Returns a `resolved` dict mapping name strings to UUIDs. |
| `draft_existing_interaction` | None (pure DB) | Fetches the most recent `Interaction` record for a named HCP (ordered by `created_at DESC`). Serialises it to a dict matching Redux `formSlice` keys, applies any `updates` dict in memory without writing to the DB, and returns the full draft including `interaction_id`. |

### State Synchronization

The `state_synchronizer` node emits two SSE events per turn, both yielded from `main.py:event_generator()`:

1. **`event: form_update`** — the merged `form_state` dict, passed through `map_to_frontend_keys()` which filters the dict to only known Redux slice keys and drops falsy values.
2. **`event: validation_errors`** — the `validation_errors` list from the synchronizer, dispatched to a dedicated `setValidationErrors` Redux reducer so it cannot pollute the form state.

The frontend SSE decoder (`api.js:89–131`) splits the byte stream on `\n\n`, parses `event:` and `data:` lines from each frame, and dispatches to the appropriate Redux action (`updateFormState`, `setValidationErrors`, or `appendStreamText`). The `updateFormState` reducer explicitly destructures and discards any `validation_errors` key before spreading the payload, preventing accidental cross-contamination.

---

## Resilient Engineering & Fail-Safes

### 1. SSE Stream Exception Containment

The entire `async for event in agent_app.astream(...)` loop in `main.py:77–95` is wrapped in a `try/except Exception`. If any tool throws, the graph crashes, or the LLM call fails mid-stream, the exception is caught and yields a graceful `text_chunk` SSE event directly to the chat bubble:

```python
except Exception as e:
    yield f"event: text_chunk\ndata: {json.dumps({'text': f'\\n\\n[System Error: {str(e)}]'})}\\n\\n"
```

The `StreamingResponse` connection stays open and the user sees the error inline rather than a dropped connection or a silent freeze.

### 2. "Pull, Draft, Overwrite" Pattern for Historical Edits

The `draft_existing_interaction` tool implements a deliberate three-phase pattern for editing previously submitted records:

- **Pull**: Queries the database for the most recent interaction matching the HCP name.
- **Draft**: Serialises the DB record into an in-memory dict and applies any immediate `updates` argument without touching the database.
- **Overwrite**: The draft (including `interaction_id`) is merged into the Redux form state via the `state_synchronizer`. When the user explicitly clicks "Log Interaction", `submitInteraction()` in `api.js:48–50` detects `formState.interaction_id` is set and issues a `PATCH /api/v1/interactions/{id}` instead of a `POST`, overwriting the record atomically.

No DB write occurs during the AI drafting phase — only on explicit user confirmation.

### 3. Lenient `Dict[str, Any]` Schema for LLM Patch Updates

`edit_interaction` uses `EditInteractionSchema` with a single `updates: Dict[str, Any]` field rather than a typed per-field patch model. This is a deliberate choice: a typed patch schema would silently drop fields the LLM attempts to set if it hallucinates a field name not in the schema (e.g. `materials` instead of `materials_shared`). The `Dict` approach captures whatever the LLM returns, and field validity is enforced downstream in `state_synchronizer`'s merge loop and in the `PATCH /api/v1/interactions/{id}` endpoint which uses `InteractionUpdate.model_dump(exclude_unset=True)` before writing.

### 4. Request Cancellation via `AbortController`

`ChatPanel.jsx:12` maintains an `abortControllerRef`. On send, a new `AbortController` is created and its `signal` is passed through `streamChat()` to the `fetch()` call (`api.js:76`). A "Stop" button replaces the send button while `isGenerating` is true. Clicking it calls `abortControllerRef.current.abort()`, which cancels the in-flight fetch. The `streamChat` catch block checks `error.name === 'AbortError'` and suppresses the error silently (`api.js:134–135`), avoiding a spurious `[Error: Connection failed]` message in the chat.

---

## API Reference

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Health check — returns `{"message": "AI-First CRM API is running."}` |
| `POST` | `/api/v1/chat/stream` | Accepts `{message: str, current_form_state: dict}`. Runs the LangGraph agent and returns a `text/event-stream` SSE response with `form_update`, `validation_errors`, and `text_chunk` events. |
| `GET` | `/api/v1/hcps/search?q={query}` | Case-insensitive HCP name typeahead. Returns `List[HCPResponse]`. Used by `submitInteraction()` on the frontend to resolve HCP names to UUIDs before form submission. |
| `POST` | `/api/v1/interactions` | Creates a new interaction record. Handles HCP create-or-find logic, then inserts `Interaction`, `Attendee`, `Material`/`InteractionMaterial`, `Sample`/`InteractionSample`, and `FollowUpAction` records in a single transaction with `db.rollback()` on any exception. |
| `PATCH` | `/api/v1/interactions/{interaction_id}` | Updates a previously submitted interaction. Uses `InteractionUpdate.model_dump(exclude_unset=True)` to apply only the fields present in the request body. Calls `db.rollback()` on failure. |

---

## Database Schema

All tables use UUID v4 primary keys (PostgreSQL `UUID` type). All tables inherit `created_at` and `updated_at` timestamp columns from `TimeStampedModel`.

- **`hcps`** — Healthcare Professionals. Fields: `id`, `name` (indexed), `specialty`.
  - One-to-many → `interactions`

- **`interactions`** — Core interaction record. Fields: `id`, `hcp_id` (FK → `hcps.id`, NOT NULL), `interaction_type`, `interaction_date` (Date), `interaction_time` (Time), `topics_discussed`, `sentiment` (Enum: Positive/Neutral/Negative), `outcomes`.
  - Many-to-one → `hcps`
  - One-to-many → `attendees`, `interaction_materials`, `interaction_samples`, `follow_up_actions` (all with `CASCADE DELETE`)

- **`attendees`** — People present during the visit. Fields: `id`, `interaction_id` (FK → `interactions.id`, CASCADE), `name`.

- **`materials`** — Unique catalogue of promotional materials. Fields: `id`, `name` (UNIQUE).
  - Many-to-many with `interactions` via `interaction_materials`

- **`interaction_materials`** — Join table. Fields: `id`, `interaction_id` (FK, CASCADE), `material_id` (FK, CASCADE).

- **`samples`** — Unique catalogue of drug samples. Fields: `id`, `name` (UNIQUE).
  - Many-to-many with `interactions` via `interaction_samples`

- **`interaction_samples`** — Join table. Fields: `id`, `interaction_id` (FK, CASCADE), `sample_id` (FK, CASCADE).

- **`follow_up_actions`** — Tasks generated after the visit. Fields: `id`, `interaction_id` (FK, CASCADE), `description`, `is_ai_suggested` (Boolean), `status` (default: "Pending").

---

## Setup & Local Development

### Prerequisites

- Python 3.10+
- Node.js 18+
- A Supabase project with connection pooling enabled (Transaction mode, port 6543)
- A Groq API key

### Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
# Create backend/.env with the following variables:
# DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-<region>.pooler.supabase.com:6543/postgres
# GROQ_API_KEY=gsk_...
# SUPABASE_URL=https://<project-ref>.supabase.co   (optional, not used by ORM layer)
# SUPABASE_KEY=sb_publishable_...                  (optional, not used by ORM layer)

# Run (tables are created automatically on startup via Base.metadata.create_all)
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Vite dev server starts at http://localhost:5173
```

The frontend hardcodes `BASE_URL = 'http://localhost:8000/api/v1'` in `src/services/api.js`. No proxy configuration is required because the backend enables CORS for all origins.

---

## Known Limitations

1. **No automated tests.** There is a `test_agent.py` and `test_prompts.py` in the backend directory but no test framework (`pytest`) is in `requirements.txt`. The self-tests must be run manually and are not wired to any CI.

2. **Single HCP per interaction.** The schema models one `hcp_id` per `Interaction` row. Multi-HCP visits (e.g. a group presentation) are not supported — additional attendees are stored in the `attendees` table only as free-text names, not as linked HCP records.

3. **`interaction_date` and `interaction_time` default to server time at submission.** `api.js:34–35` uses `new Date()` at the moment the user clicks "Log Interaction", not the actual visit date. The AI extraction pipeline does not attempt to parse dates from free text.

4. **`draft_existing_interaction` ORM attribute bug — fixed.** The original implementation accessed flat attributes (`hcp_name`, `attendee_names`, `materials_shared`, `samples_distributed`, `follow_up_actions`) directly on the `Interaction` model, none of which exist as columns. The `Interaction` model stores those via ORM relationships (`hcp`, `attendees`, `materials`, `samples`, `follow_ups`). All five accesses were corrected to walk the actual relationships: `hcp_name` is now read from `recent_interaction.hcp.name`; attendee names from `[a.name for a in recent_interaction.attendees]`; material names from `[m.material.name for m in recent_interaction.materials]`; sample names from `[s.sample.name for s in recent_interaction.samples]`; and follow-up actions from `[{"description": f.description, "is_ai_suggested": f.is_ai_suggested, "status": f.status} for f in recent_interaction.follow_ups]`. Two additional serialisation bugs were fixed at the same time: `sentiment` (a `SentimentEnum` instance) is now cast to `.value` before JSON serialisation, and `interaction_date`/`interaction_time` (Python `date`/`time` objects) are cast to `str()`.

5. **`langchain-groq` and `langgraph` are unpinned.** `requirements.txt` specifies no version for these packages, which means `pip install` will pull the latest release and may introduce breaking changes across installations.

6. **CORS is fully open.** `allow_origins=["*"]` with `allow_credentials=True` is intentionally permissive for local development but is not production-safe.

7. **No HCP deduplication logic on the AI side.** If a rep types "Dr. Sarah Chen" once and "Dr. Chen" another time, the backend's `create_interaction` handler will create two separate HCP records. The `search_hcp_history` tool uses `ilike` which would match both, but the form submission path uses an exact-name match.

8. **Sentiment is stored as a database Enum (`Positive`/`Neutral`/`Negative`) but is passed as a plain string by the AI tools.** If the LLM returns a variant not in `SentimentEnum`, the `POST /api/v1/interactions` endpoint will raise a Pydantic validation error and the submission will fail with HTTP 400.
