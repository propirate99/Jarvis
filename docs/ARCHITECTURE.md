# JARVIS 1B — Isolated Multi-Module Architecture & Specification

## 1. Executive Summary

JARVIS 1B is a local-first, privacy-respecting personal assistant designed to manage six distinct life focus areas:
1. **`overview`** — Executive mission control and cross-domain status briefings.
2. **`budget`** — Monthly financial auditing, category expense breakdowns, and savings calculations.
3. **`assignments`** — Coursework deadlines, submission tracking, and study prioritization (never solving homework).
4. **`events`** — Gatherings, workshops, milestones, venue planning, and logistics checklists.
5. **`recovery`** — Confidential habit and urge check-ins, trigger reflections, and harm-reduction support.
6. **`behaviour`** — Daily routine tracking and time management derived strictly from logged activities.

Every sidebar option has **strictly isolated chat state**, **isolated conversation memory**, and **isolated data structures**—with **zero cross-tab interference**—while sharing **one reusable chat UI shell** and **one underlying AI runtime** (FastAPI + local Ollama `llama3.2:1b`).

---

## 2. Architecture Diagram (Gap-Free Grid Alignment)

```
+===================================================================================================================+
|                                              JARVIS 1B ARCHITECTURE                                               |
+===================================================================================================================+
|                                                                                                                   |
|  FRONTEND LAYER (Next.js 16 + React 19 Client Store)                                                              |
|  +-------------------------------------------------------------------------------------------------------------+  |
|  | LEFT SIDEBAR (Glass Floating Nav)                                                                          |  |
|  | [ Overview ]  [ Budget ]  [ Assignments ]  [ Events ]  [ Recovery ]  [ Behaviour ]                          |  |
|  +-------------------------------------------------------------------------------------------------------------+  |
|                                                      |                                                            |
|                                                      v activeModule selection                                     |
|  +-------------------------------------------------------------------------------------------------------------+  |
|  | ISOLATED CLIENT STATE DICTIONARY (Record<ModuleId, ModuleChatState>)                                        |  |
|  |                                                                                                             |  |
|  |  [overview]    -> { messages: [], draft: "", isLoading: false, error: null, scrollPos: 0 }                 |  |
|  |  [budget]      -> { messages: [], draft: "", isLoading: false, error: null, scrollPos: 0 }                 |  |
|  |  [assignments] -> { messages: [], draft: "", isLoading: false, error: null, scrollPos: 0 }                 |  |
|  |  [events]      -> { messages: [], draft: "", isLoading: false, error: null, scrollPos: 0 }                 |  |
|  |  [recovery]    -> { messages: [], draft: "", isLoading: false, error: null, scrollPos: 0 }                 |  |
|  |  [behaviour]   -> { messages: [], draft: "", isLoading: false, error: null, scrollPos: 0 }                 |  |
|  +-------------------------------------------------------------------------------------------------------------+  |
|                                                      |                                                            |
|                                                      v renders in gap-free 2-column grid                          |
|  +-------------------------------------------------------+-----------------------------------------------------+  |
|  | COLUMN 1: DEDICATED DOMAIN WORKSPACE                  | COLUMN 2: SHARED REUSABLE CHAT SHELL                |  |
|  |                                                       |                                                     |  |
|  | <{ActiveModule}Workspace />                           | <ModuleChatPanel moduleId={activeModule}            |  |
|  |  - CRUD Forms & Metric Cards                          |                  key={activeModule} />              |  |
|  |  - Direct SQLite Data Binding                         |  - Identical Glass styling, scrolling & composer    |  |
|  |  - Zero Cross-Tab Interactivity                       |  - Isolated Message Thread, Typing & Draft Buffer   |  |
|  +-------------------------------------------------------+-----------------------------------------------------+  |
|                                                      |                                                            |
+======================================================|============================================================+
|                                                      | HTTP JSON API (/chat/{module_id}, /modules/{module_id}/...) |
|                                                      v                                                            |
|  BACKEND LAYER (FastAPI Server @ 127.0.0.1:8000)                                                                  |
|  +-------------------------------------------------------------------------------------------------------------+  |
|  | MODULE ROUTE VALIDATOR (module_id in {'overview','budget','assignments','events','recovery','behaviour'})  |  |
|  +-------------------------------------------------------------------------------------------------------------+  |
|                                                      |                                                            |
|                         +----------------------------+----------------------------+                               |
|                         |                                                         |                               |
|                         v Deterministic Record Query                              v LLM Prompt Request            |
|  +-----------------------------------------------+     +-------------------------------------------------------+  |
|  | DETERMINISTIC PYTHON ROUTER                   |     | SHARED AI RUNTIME (Local Ollama Engine)               |  |
|  |  - Instant mathematical calculation          |     |                                                       |  |
|  |  - 100% accurate database fact retrieval      |     |  Input Payload:                                       |  |
|  |  - Zero hallucination on balances / tasks     |     |   1. MODULE_SYSTEM_PROMPTS[module_id]                 |  |
|  +-----------------------------------------------+     |   2. RECORDS Slice (active module records ONLY)       |  |
|                         |                              |   3. Recent Turn History (active module ONLY, max 12) |  |
|                         |                              |   4. User Prompt                                      |  |
|                         |                              |                                                       |  |
|                         |                              |  Target: http://127.0.0.1:11434/api/chat              |  |
|                         |                              |  Model:  llama3.2:1b (temp=0.25, keep_alive=10m)      |  |
|                         |                              |  Filter: Output Leak Scrubber                         |  |
|                         |                              +-------------------------------------------------------+  |
|                         |                                                         |                               |
|                         +----------------------------+----------------------------+                               |
|                                                      |                                                            |
|                                                      v Isolated persistence                                       |
|  +-------------------------------------------------------------------------------------------------------------+  |
|  | PERSISTENCE LAYER (SQLite: data/jarvis.db)                                                                  |  |
|  |                                                                                                             |  |
|  |  ISOLATED CHAT MEMORY:                                                                                      |  |
|  |   - chat_threads   (module_id PK, title, created_at, updated_at)                                            |  |
|  |   - chat_messages  (id PK, module_id FK, role, content, created_at)                                         |  |
|  |                                                                                                             |  |
|  |  ISOLATED DOMAIN TABLES:                                                                                    |  |
|  |   - budget_transactions (id PK, transaction_type, amount_paise, category, description, transaction_date)     |  |
|  |   - assignments         (id PK, title, subject, due_date, priority, status, description)                    |  |
|  |   - events              (id PK, title, event_date, event_time, details)                                     |  |
|  |   - recovery_logs       (id PK, habit, status, intensity, trigger, notes, log_date)                          |  |
|  |   - activity_logs       (id PK, activity, category, duration_minutes, tasks_completed, log_date, notes)     |  |
|  |   - preferences         (key PK, value, updated_at)                                                         |  |
|  +-------------------------------------------------------------------------------------------------------------+  |
+===================================================================================================================+
```

---

## 3. Strict Module Isolation Matrix

| Sidebar Option | Module ID | Primary Scope | SQLite Domain Table | Dedicated System Prompt Focus | Deterministic Query Target |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Overview** | `overview` | Executive mission control | Aggregates read-only | Cross-module briefing, profile, status coordination | Executive snapshot metrics |
| **Budget** | `budget` | Financial audits & tracking | `budget_transactions` | Income, expense categories, balance calculations | `budget_summary()`, transactions |
| **Assignments**| `assignments`| Academics & deadlines | `assignments` | Coursework milestones, priorities; NO homework solving | Pending assignments list |
| **Events** | `events` | Event logistics & venues | `events` | Dates, schedules, guest & venue planning checklists | Upcoming events list |
| **Recovery** | `recovery` | Habit & urge support | `recovery_logs` | Compassionate check-ins; emergency referral (112) | Recent check-in counts & log |
| **Behaviour** | `behaviour` | Daily productivity logs | `activity_logs` | Objective duration & routine analysis; no fake scores | Today's focus hours & breakdown |

---

## 4. Frontend State & Race-Condition Prevention

### 4.1 Dictionary State Store
State is maintained strictly in a dictionary keyed by `ModuleId`:
```typescript
type ModuleChatState = {
  messages: ChatMessage[];
  draft: string;
  isLoading: boolean;
  error: string | null;
  scrollPos: number;
};

type ModuleChatStore = Record<ModuleId, ModuleChatState>;
```

### 4.2 Mid-Flight Tab Switching & Race Condition Safety
When `sendMessage(moduleId)` is called:
```typescript
const targetModule = moduleId; // Stored in closure
```
All state mutations (`setStore(...)`) update **only** `[targetModule]`. If a user initiates a query in `budget` and immediately switches to `assignments`:
1. `assignments` immediately renders its own state (`isLoading: false`, its own draft, its own messages).
2. The spinner and typing indicator stay inside `budget` (never displayed in `assignments`).
3. When the async HTTP request to `/chat/budget` resolves, the reply is written exclusively to `store["budget"].messages`.
4. `store["assignments"]` remains 100% untainted.

### 4.3 Reusable Shell (`<ModuleChatPanel />`)
- Rendered with `key={activeModule}`:
  ```tsx
  <ModuleChatPanel moduleId={activeSection} key={activeSection} />
  ```
- Guarantees complete component re-mounting on tab switch without code duplication.
- Automatically saves `scrollTop` on scroll and restores `scrollPos` on mount.
- A "Clear Chat" reset in one module executes `POST /chat/{module_id}/reset`, wiping only that module's memory in both frontend state and SQLite.

---

## 5. Backend Schema & Route Isolation

### 5.1 Chat Memory Tables (SQLite)
```sql
CREATE TABLE IF NOT EXISTS chat_threads (
    module_id TEXT PRIMARY KEY CHECK(module_id IN ('overview','budget','assignments','events','recovery','behaviour')),
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (module_id) REFERENCES chat_threads(module_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_module ON chat_messages(module_id, id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(module_id, created_at);
```

### 5.2 API Routes & Route Validation
All endpoints validate `module_id`:
- `POST /chat/{module_id}`: Evaluates prechecks, handles deterministic queries, or queries Ollama using ONLY active module turn history and domain records.
- `GET /chat/{module_id}/messages`: Returns recent turn history for `module_id`.
- `POST /chat/{module_id}/reset`: Clears messages for `module_id`.
- `GET /modules/{module_id}/records`: Fetches module-scoped domain data.
- Dedicated REST routes: `/budget/...`, `/assignments/...`, `/events/...`, `/recovery/...`, `/activity-logs`, `/productivity/...`, `/overview/summary`.

---

## 6. Single Shared AI Runtime

- **Local Endpoint**: `http://127.0.0.1:11434/api/chat`
- **Model**: `llama3.2:1b` (configured with `temperature: 0.25`, `keep_alive: 10m`, `num_predict: 220`)
- **Isolation Guarantee**:
  - The AI runtime receives a self-contained payload constructed on-the-fly.
  - The payload combines `MODULE_SYSTEM_PROMPTS[module_id]`, active module records block, active module recent turns, and the user message.
  - Turns from other tabs are **never** present in the prompt.
- **Safety**:
  - Crisis detection triggers `CRISIS_REPLY` with emergency contacts (112, Tele-MANAS 14416).
  - Out-of-scope code/homework generation requests are blocked.
  - Model leakage scrubber (`scrub`) ensures persona integrity.

