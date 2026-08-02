# Asterism - Agent Guidelines

This is the canonical agent instruction file for this repository.
`CLAUDE.md` should be a symlink to this file so Claude Code and Codex share the same project context.

> A local-first personal knowledge base with an agent inside, built around a knowledge graph.

## Core Philosophy

**The Problem**: AI content grows exponentially, but human attention scales linearly.

**Our Solution**: AI handles information triage, analysis, and graph-building; humans focus on judgment and decisions.

**Key Principles**:
1. **Local-first**: Filesystem = single source of truth. The frontend is just a view over the backend's REST/SSE API.
2. **User ownership**: All AI outputs are editable. This is the user's own knowledge base.
3. **Security boundary**: All operations stay within `$ASTERISM_DATA_ROOT`.
4. **Originals are immutable**: `meta.json` and `original.*` are written once at capture and never modified; everything else is derived and regenerable.
5. **First principles, no hardcoding**: Solve problems from first principles. Avoid hardcoded rules or brittle parsing logic. When dealing with messy/unstructured data (HTML, PDFs, etc.), prefer letting the AI model interpret the content rather than writing fragile extraction code. Ensure generalizability over edge-case handling.
6. **Minimal code**: Less code is always better. **Knowing when to delete code is more important than knowing how to write it.** Don't write unnecessary code. If something can be achieved with fewer lines, do it. Actively look for code to delete - dead code, redundant logic, over-abstractions. The best code is no code.
7. **Think globally, not incrementally**: Don't just patch the immediate problem. Step back and ask: Should this be refactored? Are there similar patterns to unify? Incremental fixes accumulate into debt.

---

## Architecture

- **`backend/`** — Python/FastAPI owns everything: local-first file storage, AI provider abstraction, content ingestion/extraction, content analysis, the knowledge graph, and chat. Analysis and graph pipelines are built as LangGraph graphs (`app/analysis/graph.py`, `app/graph.py`) so individual fields checkpoint (`SqliteSaver`) and retry independently instead of redoing a whole pipeline run.
- **`frontend/`** — Next.js is a thin REST/SSE client. No business logic lives here; it talks to the backend at `NEXT_PUBLIC_BACKEND_URL` (default `http://localhost:8000`).

### Provider abstraction (`backend/app/providers/`)

A single `Provider` interface (`base.py`) with 4 implementations, selected by `config.json`:
- `cli_claude` / `cli_codex` — invoke the user's own signed-in `claude`/`codex` CLI via subprocess. No separate API key.
- `api_anthropic` / `api_openai` — direct API key.

`config.json` (at `$ASTERISM_DATA_ROOT/config.json`):
```json
{
  "strategy": "cli",
  "provider": "claude",
  "api_key": null,
  "embeddings_api_key": "sk-..."
}
```
`strategy` is `"cli"` or `"api-key"`; `provider` must match the strategy (see `CLI_PROVIDERS`/`API_KEY_PROVIDERS` in `config_repository.py`). `embeddings_api_key` is separate and always required for the knowledge graph feature — Anthropic has no embeddings endpoint and CLI providers can't embed at all, so embedding calls always go to OpenAI directly regardless of the chat/completion provider chosen above.

Keep provider-specific spawn/protocol details (e.g. Codex's `app-server --stdio` lifecycle) inside the provider layer — core app code calls the shared `Provider` interface, never `claude`/`codex` directly.

---

## File System Architecture

```
{ASTERISM_DATA_ROOT}/
├── config.json                     # agent provider strategy + keys (see above)
├── .index/
│   └── graph.db                    # SQLite knowledge graph (global, not per-source)
├── library/
│   └── {id}/
│       ├── meta.json                # IMMUTABLE: metadata captured at creation
│       ├── original.html            # IMMUTABLE: raw HTML from capture (URL sources)
│       ├── content.md               # DERIVED: extracted/processed content
│       ├── analysis.json            # DERIVED: Triage/Digest/Critique/Claims/Connections
│       ├── highlights.json          # DERIVED: saved highlights, feed the concept graph
│       ├── feedback.json            # DERIVED: per-point up/down ratings on analysis fields
│       ├── chat/{conversation_id}.json  # DERIVED: one file per chat conversation
│       └── error.txt                # Only present if ingestion/analysis failed
└── wiki/                            # DERIVED: regenerable projection of graph.db
    ├── {slug}.md                    # one page per qualifying concept
    ├── index.md                     # regenerated catalog
    └── log.md                       # append-only compile history
```

### meta.json (Immutable)

Written once at capture time, **never modified**:
```json
{
  "id": "abc123",
  "created_at": "2026-01-28T...",
  "type": "html",
  "source_url": "https://...",
  "original_file": "original.html",
  "original_title": "Page title at capture time"
}
```

### Processing Status (File-based)

Status is **inferred from file existence**, not stored:

| State | Files Present |
|-------|---------------|
| Processing | `meta.json` only |
| Ready | `meta.json` + `content.md` + `analysis.json` |
| Failed | `meta.json` + `error.txt` |

Because status is inferred this way, any writer that touches the `meta.json`/`original.*`/`content.md` triad must treat the write as a mini-transaction: guard it, and on failure leave `error.txt` rather than a partial directory that looks identical to "still working" (see `create_source_from_url` in `backend/app/repositories/source_repository.py`).

### Reanalyze operation

1. Read metadata from `meta.json`.
2. Read raw content from `original.html` (or re-fetch if URL-based).
3. Re-extract content → update `content.md`.
4. Re-run the analysis graph → update `analysis.json`.
5. **NEVER** modify `meta.json` or `original.html`.

**Why this matters**: some captures (e.g. a future browser-extension capture of a logged-in/JS-rendered page) can produce HTML that a server-side fetch can never reproduce. Overwriting original with re-fetched content destroys irreplaceable data.

### The knowledge graph (`.index/graph.db`)

Two tiers, both feeding the same embed → dedup pipeline (`app/concept_graph/`):
- **Tier 1 (automatic)**: every analyzed source's `digest.concepts` becomes a graph node, no user action required.
- **Tier 2 (user-driven)**: highlights the user explicitly saves are richer nodes, extracted the same way.

High-confidence dedup merges auto-apply; ambiguous ones (and anything classified `contradicts`) queue for review (`GET /graph/review-queue`). The wiki compile layer (`app/wiki/`) renders `graph.db` into browsable markdown — `graph.db` is always the source of truth; wiki pages are a regenerable projection, never written back into.

---

## Backend API shape (`backend/app/routers/`)

- `sources.py` — CRUD, `/analyze`, `/chats` (list/create/delete conversations), `/chat` (SSE), `/highlights`, `/feedback` (+ `/feedback/{id}/promote` into the graph).
- `graph.py` — `GET /graph`, review-queue list + resolve.
- `wiki.py` — `POST /wiki/compile` (also invocable via `backend/scripts/wiki_compile.py` from cron/launchd — no in-process scheduler by design).
- `agent.py` — `POST /agent/complete`, a thin pass-through to the provider abstraction.

---

## Frontend structure (`frontend/src/app/`)

- `/` — sources list + create form (paste URL or text).
- `/sources/[id]` — source detail: original content, analysis tabs, per-source chat with conversation switching, text-selection auto-attach as chat context.
- `/graph` — concept graph view.

There is no Dashboard, Feed, or Notebook yet — those are legacy-only features not yet ported into this frontend.

---

## Workflow Rules

### Before Committing
- **Check README.md**: Before making any git commit, review if README.md needs to be updated based on the changes made. Consider updating if:
  - New features were added
  - Setup/installation steps changed
  - API or configuration changed
  - Dependencies were added/removed

### Continuous Learning
- **Update AGENTS.md**: When discovering patterns, fixing recurring issues, or learning something that would help future development, summarize and add it to this canonical file. Examples:
  - Common pitfalls and how to avoid them
  - Architecture decisions and their rationale
  - Patterns that work well in this codebase

### Track Compromises
- **Update todo.md**: When making a pragmatic/compromise decision (e.g. "good enough for now" solutions, shortcuts, known limitations), add it to `todo.md` so we know what to revisit before launch or when scaling to more users. `todo.md` is gitignored (local-only working notes) but still maintained on disk.

### End-of-Session Summaries
- **Write a dated session summary**: After finishing a chunk of work (a plan, a multi-step task, a significant decision), write a summary to `docs/updates/sessions/M-D-<short-topic>.md` covering what was done, what's next, and links to any plans/specs touched. This lets a fresh session get oriented without requiring prior conversation history. `docs/updates/` is gitignored (local-only) but still maintained on disk.
- **Keep `docs/INDEX.md` current**: update it whenever a new plan, spec, or session summary doc is added, so it stays the single entry point for orientation. Also gitignored, still maintained.
- **`docs/ROADMAP.md`**: the ordered phase-by-phase narrative of the whole rewrite — check it for current phase status before assuming a feature is or isn't built. Also gitignored, still maintained on disk.

### Keep SDD Workspace Artifacts
- **Don't delete `.superpowers/sdd/<plan>/` after a plan finishes**: task briefs, reports, and review packages generated during subagent-driven-development stay in place as a record, rather than being cleaned up at plan completion. Note this only survives as long as the worktree does — if the worktree itself is removed later (e.g. after merge), copy anything worth keeping into a durable project location first.

---

## Lessons Learned

### Frontend: Always Extract Components
Don't write long component files. Proactively split into separate components to keep files focused and manageable.

### Agent History Must Include Tool Traces (2026-02-02)
Multi-turn agent history should include tool calls and results, not just the text responses.

Without tool traces, the agent in Turn 2 only sees "I read 26 files" but not what was in them—leading to hallucinated details when acting on that data.

### Agent Debug Logs Are Opt-In (2026-06-18)
Do not write full agent prompts/responses to disk during normal use. Enable `SECONDBRAIN_AGENT_DEBUG_LOGS=1` only for local debugging, because those logs can contain captured source text and user preferences.

### Host-Based Security Checks Must Survive Redirects (2026-07-26)
Any check keyed on a URL's hostname (login-wall detection, allow/blocklists, auth gates) that runs *before* a request which can itself follow redirects is bypassable — the check has to be re-evaluated against the final URL too, not just the input URL. Caught in code review (`fetch_url` in `backend/app/ingestion/fetcher.py` checked `LOGIN_REQUIRED_HOSTS` pre-redirect while running with `follow_redirects=True`); the bug shipped because the only test asserted `follow_redirects=True` as a constructor kwarg rather than actually simulating a redirect. For any behavior gated on a flag like this, write a test that exercises the behavior the flag enables, not just that the flag is set.

### File-Existence-Inferred Status Makes Multi-File Writes a Correctness Boundary (2026-07-26)
Because this repo infers source status (`Processing`/`Ready`/`Failed`) from which files exist rather than a stored field, any code that writes the `meta.json`/`original.*`/`content.md` triad must treat that sequence as a mini-transaction: guard it, and on failure leave a signal (`error.txt`) rather than a partial directory that looks identical to "still working." Found via `create_source_from_url` having three unguarded sequential `write_text()` calls with no cleanup on failure. Apply the same reflex to any future writer into this file-existence model (e.g. `analysis.json` generation).

### Legacy Stack Frozen (2026-08-01)
The inherited Next.js/Tauri monolith is fully frozen — no further commits, security fixes included — and untracked from git (gitignored, kept on disk as reference only). All new work happens in `backend/`+`frontend/`. If you find yourself about to edit `src/`, `src-tauri/`, or `extension/`, stop: port the fix into the rewrite instead.
