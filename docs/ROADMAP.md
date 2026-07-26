# Asterism Roadmap — Full Rewrite, All Phases

This is the single document that maps the entire rewrite goal to concrete phases, from the founding vision through to the knowledge-graph endgame. Each phase links to its detailed spec/plan/decisions doc where one exists. See `docs/INDEX.md` for the general docs index; this file is specifically the ordered roadmap.

## The Goal (from the founding vision)

Per `docs/updates/plans/7-18-customize-personal-system.md` (local-only): Asterism should become a **personal knowledge operating system centered on a knowledge graph** — not just a note-taking app, not just semantic search, not just RAG. The core idea: knowledge becomes valuable through the *relationships* discovered between pieces of it, not merely through storage. Everything below builds toward that.

Two independent motivations drive the current rewrite specifically: **ownership** (the inherited "second brain" codebase should become genuinely the user's own code, not carried-over authorship) and a **deliberate stack change** to Python + LangGraph + a real knowledge graph, replacing the inherited Next.js-does-everything architecture.

## Phase 0 — Repo Independence (DONE)

Split Asterism from its "second brain" origin into a genuinely independent repo: fresh git history, MIT attribution preserved, old full-history copy kept at `Asterism_back/` for reference. See `docs/updates/plans/7-25-second-brain-inheritance-audit.md` (local-only) and `docs/updates/sessions/7-25-repo-split-and-backend-foundation.md`.

## Phase 1 — Backend Foundation (DONE, merged to main)

Foundational vertical slice proving the new architecture end-to-end: Python/FastAPI backend owning local-first file storage (`library/{id}/meta.json` + `content.md`), a fresh Next.js frontend (list/create/detail pages) talking to it over REST. No AI logic yet.

- Architecture: `docs/superpowers/specs/2026-07-25-backend-architecture-design.md` — **the overarching decision**: Next.js becomes 100% frontend; Python/FastAPI/LangGraph becomes the entire backend (file storage, AI, analysis, knowledge graph). CLI-subprocess and API-key strategies both live inside the Python backend, not split across runtimes.
- Plan: `docs/superpowers/plans/2026-07-25-backend-foundation.md`

## Phase 2 — AI Provider Abstraction (DONE, merged to main)

Single text-completion capability (`prompt in → text out`) proven through both invocation strategies: CLI-subprocess (`claude`/`codex`, no API key — preserves the original "bring your own agent" pitch) and direct API key (Anthropic/OpenAI SDKs). This is the foundation every later AI-touching phase depends on.

All 9 implementation tasks complete via subagent-driven-development: `Provider` interface + 4 concrete providers (`cli_claude`, `cli_codex`, `api_anthropic`, `api_openai`), `config_repository`, provider `factory`, and `POST /agent/complete`. 49/49 backend tests passing; final whole-branch review approved with no Critical/Important findings; manually verified end-to-end against a real OpenAI key. Merged into `main`.

Known deferred compromise (see `todo.md`): API-key providers hardcode model name/`max_tokens`, no per-request model selection yet.

- Spec: `docs/superpowers/specs/2026-07-25-ai-provider-abstraction-design.md`
- Plan: `docs/superpowers/plans/2026-07-25-ai-provider-abstraction.md`
- Status doc: `docs/updates/sessions/7-25-ai-provider-abstraction-scoping.md`

## Phase 3 — Content Ingestion / Extraction (DONE, merged to main)

Fetching and parsing raw content (URLs, HTML, plain text) into clean text ready for analysis — the Python-side equivalent of the old app's `content.ts`.

`POST /sources` now accepts a `url` field: `app/ingestion/fetcher.py` (fetch + login-wall detection), `title.py` (og:title → `<title>` → hostname), `extractor.py` (`trafilatura` first, AI-fallback via Phase 2's provider abstraction for thin extractions), and `create_source_from_url` writing `meta.json`/`original.html`/`content.md`. Branch `content-ingestion` (10 commits ahead of `main`), pushed to `origin`, PR #2 open.

Parallax-reviewed; 4 real bugs found and fixed on the branch: non-atomic multi-file writes could leave a permanently-stuck "Processing" entry (now guarded, writes `error.txt` on failure), a redirect chain could bypass the login-wall host check (now re-checked against the post-redirect URL), a whitespace-only `<title>` tag skipped the hostname fallback (now guarded), and ingestion error paths had zero logging (now log url + exception type, no content). 85/85 backend tests passing.

Known deferred compromises (see `todo.md`): hardcoded login-wall hostname list, `analysis.json` never written (pre-existing gap, not introduced by this phase), no dedicated adversarial review yet of the AI-fallback prompt-injection surface, no SSRF guard/response-size cap/duplicate-URL detection/background-job model.

**Scope note**: per Decision 4 in the knowledge-graph decisions doc, MVP covers prose-like sources only (web articles, PDFs, plain notes, meeting transcripts). GitHub repos and other structured/code sources are explicitly out of scope until the core highlight → concept-graph loop is validated on prose. PDF/meeting-transcript ingestion is not yet implemented — only URL/HTML.

- Spec: `docs/superpowers/specs/2026-07-25-content-ingestion-design.md`
- Plan: `docs/superpowers/plans/2026-07-25-content-ingestion.md`
- Status doc: `docs/updates/sessions/7-26-content-ingestion-parallax-followup.md`

## Phase 4 — Content Analysis (DONE, redesigned prompts)

`POST /sources/{id}/analyze` turns a stored source's `content.md` into `analysis.json`: Triage, Digestion,
Critique, Claims (atomic, source-quote-anchored), and claim-level source-to-source Connections (redundant/
contradicts/related) — implemented as a LangGraph fan-out/fan-in pipeline (`app/graph.py` composing
`app/analysis/graph.py` as a subgraph), checkpointed via `SqliteSaver` so a retry only recomputes fields that
previously failed. `GET /sources/{id}` now includes the `analysis` field. 129/129 backend tests passing.

Prompt content was drafted and manually validated against `sample_data`'s demo articles before implementation
(one real ambiguity found and fixed: highlight `text` may paraphrase, `source_quote` must be an exact substring).

Known deferred compromise (see `todo.md`): the connections coarse-filter is LLM-based, not vector-search-based —
won't scale past a library that fits in one prompt's context window; revisit once Phase 6's Kuzu/embedding
infrastructure exists.

- Spec: `docs/superpowers/specs/2026-07-26-content-analysis-design.md`
- Plan: `docs/superpowers/plans/2026-07-26-content-analysis.md`
- Decisions: `docs/updates/plans/7-26-phase4-content-analysis-decisions.md`
- Prompt validation: `docs/updates/plans/7-26-phase4-prompt-validation.md`

## Phase 5 — Chat / Copilot

Interactive streaming chat, reasoning over the user's library. Not yet scoped/spec'd. Builds on Phase 2 (streaming variant of the provider abstraction — explicitly deferred out of Phase 2's scope) and eventually Phase 6 (graph-guided retrieval, once the graph exists).

## Phase 6 — Knowledge Graph

The centerpiece of the whole rewrite. Fully decided at the design level in `docs/updates/plans/7-25-knowledge-graph-architecture-decisions.md` (local-only) — 8 decisions already made:

1. **Two-tier graph**: Tier 1 = existing source-level Knowledge Galaxy (cheap, automatic, one node per source). Tier 2 = new concept-level graph, built only from user highlights/notes (rich, triggered by engagement, not run on every ingested article).
2. **Entity dedup**: embedding filter + LLM judgment, confidence-gated — high-confidence merges auto-apply, ambiguous ones queue for batch review. A user's own note asserting a relationship overrides ambiguous embedding similarity (validated in Phase-1 prompt testing, see `docs/updates/plans/7-25-phase1-prompt-validation.md`, local-only).
3. **Copilot retrieval**: hybrid graph-guided — resolve query to concept node(s), expand 1-2 hops, pull real source passages as grounding, fall back to plain semantic search for unhighlighted content.
4. **Ingestion scope**: prose-like sources only for MVP (see Phase 3 note above).
5. **Storage**: Kuzu (embedded, Cypher-like, no server process) — chosen over Neo4j (adds a server dependency) and NetworkX (fine for prototype, not long-term).
6. **Notes ↔ graph integration**: the user's own written notes are highlighted the same way as sources, feeding the same extraction pipeline — this is what makes it a *personal* knowledge graph rather than a reader + a separate notes app.
7. **Sub-phase roadmap** (within this phase): (a) prompt validation — done, see the Phase-1 doc; (b) graph-only service — build Kuzu store + concept nodes from existing `highlights.json`, no copilot changes; (c) copilot integration — wire the concept graph into hybrid retrieval last.
8. **User-seeded entities**: top-down concept watchlist — user declares a term they care about, system searches internally then falls back to web search (reusing the existing Brave key integration), AI drafts a definition, user approves synchronously (unlike per-highlight dedup, this is a deliberate action so blocking is fine).

Open questions not yet resolved (deferred until this phase is actually picked up): adapter design for code/structured sources, per-speaker highlight semantics for meeting transcripts, concrete dedup confidence thresholds (needs empirical tuning), where the "seed an entity" UI action lives.

## Phase 7 — Extension Rewrite

The browser extension (`extension/*.js` in the inherited codebase) is a separate, smaller surface — own-authorship rewrite, independent of the Next.js/Python work above. Not yet scoped.

## Phase 8 — Desktop Shell (Tauri) — Lowest Priority, Deferred

Per `todo.md`'s "Deferred: macOS desktop app" section — path not established, out of scope until the OSS web launch track is further along. Decisions already made: Tauri over Electron (lightweight), notarize+DMG distribution, port 41932 for desktop mode.

## Post-MVP / Future Ideas (Not Committed)

See `docs/updates/plans/post-mvp-ideas.md` (local-only) — e.g. proactive trend/terminology tracking (system periodically scans for emerging terms in the user's areas of interest, rather than only reacting to user-seeded entities). Explicitly parked, not scheduled into any phase above.

## How Phases Relate (Dependency Order)

```
Phase 0 (repo split) ──▶ Phase 1 (backend foundation) ──▶ Phase 2 (AI provider abstraction)
                                                                    │
                              ┌─────────────────────────────────────┼─────────────────────────┐
                              ▼                                     ▼                         ▼
                    Phase 3 (ingestion)                  Phase 5 (chat, streaming)   Phase 4 depends on
                              │                                     │                 both 2 and 3
                              ▼                                     │
                    Phase 4 (content analysis) ─────────────────────┤
                              │                                     │
                              ▼                                     ▼
                    Phase 6 (knowledge graph) ◀─────────────────────┘
                              │
                              ▼
                    Phase 6c (copilot graph integration, needs Phase 5 + Phase 6b)

Phase 7 (extension) and Phase 8 (desktop) are independent side-tracks, not on this critical path.
```

Each phase gets its own brainstorm → spec → plan → subagent-driven-development cycle, same as Phases 0-2. This doc should be updated whenever a phase completes or a new one is scoped.
