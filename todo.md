# TODO

## Open (web app / OSS launch)

- [ ] Submit the extension to the Chrome Web Store ($5 one-time, ~1-3 day review).
      This is the real fix for install friction — every unpacked-install flow in the
      dashboard banner is interim. After listing, point the banner's Install button
      straight at the store page (2 clicks total).

- [x] Real demo GIF for the README hero (recorded from the live app; replaced the placeholder SVG)
- [ ] Re-record the hero GIF as one single "Skip moment": paste link → triage card appears →
      verdict says Skip (45 min saved). One loop, no product tour — this is the acquisition hook.
      Secondary asset for a follow-up post: the Contradicts connection card.
- [ ] Rotate the local Brave Search API key before publishing (never committed; disk hygiene)
- [ ] Long articles can fail to process (e.g. paulgraham.com/greatwork.html, ~9k words).
      Worked around by pointing the extension welcome-page example at a shorter essay
      (do.html) — investigate the real limit (agent timeout? prompt size?) and fix.

### Compromises (revisit before launch / scaling)
- **Content analysis — source-level connections use LLM coarse-filter, not vector search**: Phase 4's claim-level
  connection finder (new source's claims vs. the library) uses a two-phase LLM approach — cheap LLM call to shortlist
  ~5 candidate sources from brief summaries, then a detailed LLM call comparing full claim lists only against those
  candidates. This does not scale past a library that fits in the coarse-filter prompt's context window (roughly
  low-hundreds of sources for a single user). CLAUDE.md's own philosophy doc already flags this as "MVP: brute-force
  comparison; future: vector search" — the real fix is embedding-based retrieval, but that infra is already committed
  to Phase 6 (Kuzu-based concept graph, Decision 2 in the knowledge-graph decisions doc) for the Tier-2 graph. Revisit
  reusing that same embedding infra for Tier-1 source-level connections once Phase 6 lands, rather than building a
  second vector store just for this.
- **Content analysis — SqliteSaver checkpoint DB has no pruning**: `.cache/analysis_checkpoints.db`
  (`backend/app/graph.py`) grows one thread per analyzed source forever, and the retry-only-failed-fields behavior is
  actually driven by `analysis.json` (via `read_analysis` seeding `result` back into the graph), not by the
  checkpointer's own persisted state — so the checkpoint DB is carrying real cost (unbounded growth, a possible
  "database is locked" surface if two `POST /sources/{id}/analyze` calls for different sources land concurrently
  under FastAPI's threadpool, both touching the same sqlite file) for comparatively little functional payoff. Found
  in the Phase 4 final review. Revisit: either prune old threads periodically, or drop the checkpointer and rely on
  `analysis.json` alone (would need to re-verify LangGraph's parallel-node execution still works without one).
- **Content analysis — `analysis.json` writes are not atomic, no corruption guard on read**: `write_analysis`
  (`backend/app/repositories/source_repository.py`) uses a plain `write_text`, and `read_analysis` calls
  `AnalysisResult.model_validate_json` with no try/except. A crash mid-write would leave a truncated file that then
  raises an uncaught `ValidationError` (500) on the next `GET /sources/{id}` or connections lookup. Low probability
  for a single-user local tool; found in the Phase 4 final review. Revisit with a temp-file + atomic rename on write,
  and a caught-and-return-None (or surfaced as a distinct error) on read.
- **Content analysis — failed connections comparison is indistinguishable from "no connections found"**:
  `find_connections` (`backend/app/analysis/connections.py`) returns `{"connections": []}` on any provider/parse
  failure in either phase, with no `connections_error` field the way the other four analysis fields
  (`triage_error`/`digest_error`/`critique_error`/`claims_error`) have. A UI can't tell "genuinely no connections"
  from "the comparison call failed." Found in the Phase 4 final review. Revisit by adding a `connections_error`
  sibling field to `AnalysisResult`.
- **URL ingestion — hardcoded login-wall hostname list**: `LOGIN_REQUIRED_HOSTS = {"x.com", "twitter.com"}`
  (`backend/app/ingestion/fetcher.py`) is a narrow special case that conflicts with this repo's "no hardcoding, let AI
  interpret messy content" principle. Any other paywalled/login-walled site's teaser HTML is silently accepted (2xx) and
  persisted as the immutable `original.html`, with no error signal. The real fix (AI-detected login walls from page content)
  is a bigger feature than a same-PR patch — revisit once ingestion has a general "low-confidence capture" signal.
- **URL ingestion — `analysis.json` is never written**: neither `create_source` nor `create_source_from_url`
  (`backend/app/repositories/source_repository.py`) write `analysis.json`, so per CLAUDE.md's own file-existence status
  model every source reads as permanently "Processing" (never "Ready") until a separate analysis step exists. Pre-existing
  gap, not introduced by content ingestion — revisit once the Digestion/Critique/Claims analysis pipeline is built.
- **URL ingestion — prompt-injection surface in the AI extraction fallback**: `extract_content`'s AI-fallback path
  (`backend/app/ingestion/extractor.py`) pipes up to 120k chars of raw, attacker/website-controlled HTML into a prompt sent
  via subprocess to the user's configured CLI agent. Flagged independently by 3/4 Parallax review dimensions on PR #2.
  Needs a dedicated follow-up review of whether the CLI sandbox/tool-restriction flags actually hold under adversarial
  page content — not a same-PR fix.
- ~~**URL ingestion — no SSRF guard beyond the login-host check**~~ — **Fixed 2026-08-01.** `fetch_url`
  (`backend/app/ingestion/fetcher.py`) now resolves and validates the hostname's IP (rejects
  private/loopback/link-local/reserved/multicast/unspecified ranges via stdlib `ipaddress`) and restricts to
  `http`/`https` schemes, checked proactively before *every* hop of a redirect chain (not just the initial URL) —
  redirects are now followed manually, bounded at `MAX_REDIRECTS = 5`. This closes the same class of gap as the
  pre-existing login-wall redirect check, using the identical pattern. **Residual, accepted risk**: no connect-time
  IP pinning, so a narrow DNS-rebinding TOCTOU window remains (attacker's domain resolves public at check-time, flips
  private before the real connection) — judged low-probability for this app's local single-user threat model;
  revisit with a custom `httpx` transport if that threat model changes. Response-size cap remains a separate, still-open
  item below. Tests: `backend/tests/test_ingestion_fetcher.py` (direct private-IP block, redirect-chain-to-private-IP
  block, non-http(s) scheme block, too-many-redirects, DNS-failure handling).
- **URL ingestion — no response-size cap**: full HTML body is buffered in memory and written whole to `original.html`,
  no `Content-Length` precheck or streaming limit.
- **URL ingestion — no ingestion-specific timeout / background job model**: bounded at 600s by pre-existing CLI-provider
  code but wired synchronously into `POST /sources`. Ties into the existing "long articles can fail to process" item above.
- **URL ingestion — no duplicate-URL detection**: every `POST /sources {"url": ...}` re-runs fetch+extract, including the
  slow AI-fallback path, even for an identical repeated request.
- **URL ingestion — minor error-handling inconsistencies**: URL-ingestion failures return `{error_type, message}`
  (`AgentErrorResponse`, originally modeled for the unrelated `/agent/complete` endpoint) while other 400/404s in the same
  router raise plain `HTTPException`; `title=""` is rejected but `content=""` is still accepted; `str(exc)` for
  `ConfigError`/provider errors is returned verbatim to the client (interpolates the absolute `data_root` path). No current
  frontend caller depends on any of these — unify before one is wired up.
- **Backend AI provider abstraction — no model selection for API-key strategy**: `AnthropicApiProvider`/`OpenAiApiProvider`
  (`backend/app/providers/api_anthropic.py`, `api_openai.py`) hardcode `MODEL` (`claude-sonnet-4-5`, `gpt-4o`) and `MAX_TOKENS`
  constants with no config override. Fine for the single-capability MVP pass (see
  `docs/superpowers/specs/2026-07-25-ai-provider-abstraction-design.md`), but users on the api-key strategy can't pick a
  model. Revisit alongside a future `config.json` `model` field.
- **Content ingestion — title unsafe against literal `---` in frontmatter body-split**: `create_source`/`create_source_from_url`
  (`backend/app/repositories/source_repository.py`) now `json.dumps()` the title before writing it into `content.md`'s YAML
  frontmatter, which correctly escapes embedded `"` characters. A title containing the literal substring `---` can still
  corrupt `get_source`'s `raw.split("---", 2)` body-extraction logic, since `json.dumps` doesn't escape hyphens. Low impact —
  `get_source` reads the title from `meta.json` (properly JSON-escaped), not from the frontmatter, so only `content` would be
  corrupted, and only for titles containing that exact substring (increasingly plausible now that titles come from arbitrary
  `og:title` values, not just user-typed text). Revisit with a proper frontmatter serializer (e.g. `yaml.safe_dump`) if this
  becomes a real problem.
- **Extension server discovery**: probes ports 3000-3003 + 41932 in parallel and
  verifies an `app: "secondbrain"` marker before sending page content; caches the
  last-good port. Good enough for local use — replace with Chrome Native Messaging
  for public distribution (industry standard: 1Password, Bitwarden, KeePassXC).
- **Agent CLI dependency**: Claude Code or Codex CLI must be installed separately.
  Future providers should plug into the agent provider layer.
- **Seeding guard is process-cached**: `ensureUserDataInitialized` caches per-path
  initialization for the server's lifetime; deleting the data folder while the
  server runs won't re-seed until restart. Edge case, acceptable.
- **Frontend analysis types are hand-mirrored from backend schemas**: `frontend/src/lib/api.ts`'s TypeScript
  interfaces (`Triage`, `Digest`, `Critique`, `Claim`, `Connection`, `AnalysisResult`, etc.) are manually kept in sync
  with `backend/app/schemas/analysis.py`, with nothing enforcing that sync. A field rename on either side becomes a
  silent runtime `undefined` in the UI rather than a compile error. Found in the Phase 4.5 final review. **Why:** no
  schema-codegen tooling exists in this repo yet. Revisit with a FastAPI OpenAPI export → `openapi-typescript`
  pipeline (or similar) when the backend schema next changes.
- **Triage card has no error affordance when `triage_error` is set**: `frontend/src/app/sources/[id]/page.tsx` only
  renders the `TriageCard` when `analysis?.triage` is truthy. If `triage` is `null` with `triage_error` set — a real
  partial-failure state the backend can produce, same as the other three analysis fields — the user sees nothing at
  all: no card, no error, no retry affordance, unlike Digest/Critique/Claims which each render `AnalysisSectionError`
  in that case. Found in the Phase 4.5 final review. **Why:** this was a gap in the original design spec, not a
  deviation during implementation — the spec said the Triage card is "rendered whenever `analysis?.triage` is
  present" without covering the error case. Revisit by rendering an `AnalysisSectionError` in the Triage card's place
  when `triage_error` is set, mirroring the pattern already used by the other three tabs.
- **Chat copilot — no real CLI-provider streaming yet**: `cli_claude`/`cli_codex` providers (`backend/app/providers/`)
  implement `stream_complete()` via the single-chunk fallback (run the subprocess to completion, then yield the whole
  response as one chunk) rather than incrementally forwarding partial output as it's produced. Only the
  `api_anthropic`/`api_openai` providers stream token-by-token today. **Why:** already called out as
  "Out of Scope (Deferred)" in `docs/superpowers/specs/2026-07-29-chat-copilot-design.md` — the CLI providers'
  underlying subprocess protocols don't expose incremental output in a form the current adapter layer parses yet.
  Revisit if CLI-provider users report chat feeling unresponsive compared to the API-key strategy.
- **Chat copilot — no prompt truncation/summarization strategy**: `build_chat_prompt`
  (`backend/app/chat/prompts.py`) concatenates the full source content, full analysis summary, and the entire
  conversation history into one prompt with no length cap. A long source plus a long-running conversation can exceed
  a provider's context window with no graceful degradation (e.g. summarizing older turns, truncating source content).
  **Why:** already called out as "Out of Scope (Deferred)" in `docs/superpowers/specs/2026-07-29-chat-copilot-design.md`
  — needs a real strategy (sliding window, summarization pass, or token-aware truncation), not a quick patch. Revisit
  once real usage data shows how often sources/conversations approach context limits.
- **No eval harness for LLM extraction quality (entities, claims, digest, critique) — design decided, blocked on data volume**: every test for `backend/app/analysis/*` and `backend/app/concept_graph/*` mocks the LLM provider with hand-written JSON — zero tests exercise a real model call, and there's no golden dataset or precision/recall measurement anywhere. The only quality check that ever existed (`docs/updates/plans/7-25-phase1-prompt-validation.md`) is a manually-simulated, 7-example, self-authored sample that its own author flagged as biased toward easy cases, with an explicitly-identified gap (no-note related-but-distinct concepts) never closed with real data. **Why:** surfaced in the 2026-08-01 whole-system review (`docs/updates/sessions/8-1-system-review.md`) — this is the root cause of low confidence in entity-extraction quality specifically. Revisit before/alongside starting Phase 6c, since retrieval built on unmeasured extraction quality makes retrieval bugs indistinguishable from extraction bugs.
  **Next step**: full design brainstormed and written to `docs/superpowers/specs/2026-08-01-concept-graph-eval-harness-design.md` (local-only, gitignored) — scoped to `concept_graph/` extraction + dedup only (Phase-4 analysis deferred to a later pass), two separate golden datasets (extraction: real highlights/digests + hand-built edge cases; dedup: mined from real `graph.db` comparison history + hand-built edge cases), dedup scored by exact-label match, extraction scored by a Cohen's-kappa-calibrated LLM-judge, 30+ cases per dataset target, standalone manual CLI script (not CI), git-tracked timestamped reports. **Blocked on**: not enough real library data yet (highlights + `graph.db` comparison history) to actually build the two golden sets — implementation plan (`writing-plans`) intentionally not written yet. Revisit once the library has enough real highlights/digests and enough `graph.db` history to source both datasets from real usage rather than needing to fabricate the majority of cases.
- **Concept-graph prompts are prompt-only JSON with weak enum validation, no retry, no few-shot examples**: `concept_graph/prompts.py`'s `_validate_shape()` checks required keys exist but not that `judgment`/`relationship`/`confidence` are valid enum values (an out-of-enum `relationship` silently falls back to `"related"`); the extraction/dedup calls are single-shot with no retry, unlike the Phase-4 analysis nodes which retry twice and use real Pydantic `Literal[...]` enforcement. **Why:** found in the 2026-08-01 system review. Industry practice favors tool-use/function-calling schema enforcement over prompt-only JSON for exactly this failure mode (near-100% schema compliance vs. prompt-only's malformed/inconsistent output) — revisit by switching to tool-forced structured output where the provider supports it, and adding enum validation + retry to match the Phase-4 pattern.
- **[ACCEPTED RISK, will not fix] Legacy `src/lib/content.ts` has the same redirect/login-wall bypass bug already fixed in the backend**: `requiresAuthentication()` is checked once before `fetch()`, never re-checked against `response.url` after redirects resolve — this is the exact bug CLAUDE.md's "Lessons Learned" section documents as fixed in `backend/app/ingestion/fetcher.py`, left unpatched in the legacy twin. **Why:** found in the 2026-08-01 system review. Per the 2026-08-01 legacy-freeze decision (`docs/superpowers/specs/2026-08-01-legacy-freeze-decision-design.md`), legacy `src/` is now fully frozen — no further commits of any kind, including this fix. Accepted risk, not a revisit item.
- **[ACCEPTED RISK, will not fix] `/api/capture` (legacy) has wildcard CORS + no auth + no SSRF guard on a server-side fetch of an arbitrary client-supplied URL**: `Access-Control-Allow-Origin: *` plus zero authentication means any webpage the user's browser visits while the legacy server is running on localhost could POST a URL and trigger a server-side fetch to an internal target (e.g. cloud metadata endpoints, other localhost ports) — a real, not theoretical, drive-by SSRF vector. Neither fetcher in either stack has a private/link-local IP denylist, response-size cap, or redirect-count cap. **Why:** found in the 2026-08-01 system review. Per the 2026-08-01 legacy-freeze decision, legacy `src/` is frozen — this will not be patched there. The backend (`backend/app/ingestion/fetcher.py`) half of this finding is **fixed** (see the IP-denylist entry above); legacy's copy remains an accepted risk, unpatched.
- **`create_source` (plain-text path, backend) lacks the atomic-write guard `create_source_from_url` already has**: unguarded sequential `write_text()` calls with no try/except and no `error.txt` on partial failure — same failure class CLAUDE.md's own "Lessons Learned" entry describes as fixed, left unfixed on the sibling code path. **Why:** found in the 2026-08-01 system review. Revisit by applying the same guard pattern already proven in `create_source_from_url`. (Legacy `createPendingSource` has the identical gap but is now an **accepted risk** per the legacy-freeze decision below — not a revisit item.)
- **No file locking anywhere in either stack**: `chat.json`/`highlights.json`/`feedback.json` are all read-modify-write with no `flock`/`filelock`/equivalent (confirmed zero hits repo-wide). Concurrent requests touching the same source's file (e.g. a double-click, or SSE chat racing a highlight save) can silently lose an update. **Why:** found in the 2026-08-01 system review. Revisit with a per-source-file lock or single-writer queue if concurrent-write reports surface in practice. Scope note: per the 2026-08-01 legacy-freeze decision, this only needs fixing on the rewrite (`backend/`) side — legacy `src/` is frozen and won't receive this fix.
- **New `frontend/` (the actively-developed rewrite UI) has zero tests and no CI exists anywhere in the repo**: no test files, no test script in `package.json`, no jest/vitest config; there's also no `.github/workflows` at all, so even the backend's 329 passing tests aren't gated on any merge. **Why:** found in the 2026-08-01 system review. Revisit before the rewrite frontend grows much further — right now every change to `frontend/src/lib/api.ts` or the analysis views ships with zero automated safety net.
- ~~**Two parallel stacks (legacy `src/` vs. rewrite `backend/`+`frontend/`) drift silently**~~ — **Decided 2026-08-01.** Resolved via `superpowers:brainstorming`: legacy `src/` (and `src-tauri/`) is now **fully frozen** — no further commits of any kind, security fixes included. It stays in the repo purely as reference material for porting missing functionality (Dashboard, Feed, Notebook, folder tree, desktop shell) into the rewrite. See `docs/superpowers/specs/2026-08-01-legacy-freeze-decision-design.md` for full rationale and accepted risks. **Note:** `README.md` is deliberately left unchanged by this decision — it still describes/ships legacy — revisit once the rewrite is closer to feature parity.

- ~~**Highlight creation has no duplicate detection**~~ — **Fixed 2026-07-31.** Found while manually testing the
  wiki compile layer (Phase 6d): a real source's `highlights.json` (`~/AsterismData/library/8208a857da1f/highlights.json`)
  had 14 entries with several exact-duplicate `source_quote` + `note` pairs created seconds apart — a
  double-submitted save from the SelectionToolbar UI, since `append_highlight` had no idempotency check. Fix:
  `find_duplicate_highlight` (`backend/app/repositories/source_repository.py`) does an exact, per-source,
  whitespace-normalized match on `(source_quote, note)`; `post_highlight_endpoint` returns the existing highlight
  with `HighlightProcessResult.duplicate=True` and skips `process_highlight` entirely for a match, so no second
  `concept_highlights` provenance row is created (this was the root cause of the wiki-compile duplicate-citation
  symptom, not the Phase 6b concept-graph dedup — that pipeline was already correctly collapsing repeats into one
  concept). Also added a re-entry guard in `SelectionToolbar.tsx` (`isSavingRef` + disabled buttons while a save is
  in flight) to stop the double-submit at its source. Tests: `test_post_highlight_dedupes_identical_quote_and_note`,
  `test_post_highlight_same_quote_different_note_is_not_a_duplicate` in `backend/tests/test_highlights_api.py`.

### Backend rewrite
- **Hatchling build config**: pyproject.toml requires `[tool.hatch.build.targets.wheel]` with `packages = ["app"]` because hatchling cannot auto-detect that the package directory is named "app" instead of matching the project name "asterism-backend". This is a pragmatic solution; consider aligning the directory name with the project name if the package structure changes.

### Known Risks
- A local agent CLI must be installed separately — cannot bundle Claude Code or Codex
- Agent Mode gate blocks the workspace until a provider is connected
- Brave Search API key still needed for feed web search (optional feature)

---

## Future Ideas (Inspiration)

- Medium article import: user has a Medium subscription — check whether Medium exposes
  an API (official or RSS-based, e.g. `medium.com/feed/@username` or per-publication feeds)
  that could be used to fetch and extract full article content directly, instead of relying
  on generic HTML capture for Medium URLs.

---

## Deferred: macOS desktop app (Tauri)

Path not established yet — out of scope for the OSS web launch. Kept for reference.

### Decisions made earlier
- **Packaging**: Tauri (lightweight, ~10MB vs Electron's ~150MB)
- **Distribution**: Notarize + DMG (not Mac App Store — sandbox blocks subprocess + filesystem access)
- **Port**: web mode 3000 (default), Tauri 41932
- **Native Messaging**: migrate extension ↔ app communication when distributing publicly

### Remaining desktop work (when resumed)
- [ ] Apple Developer account ($99/year) for code signing + notarization
- [ ] App icon and DMG installer design
- [ ] Auto-update mechanism (Tauri has built-in support)
- [ ] Handle `user_data/` path for macOS (`~/Library/Application Support/SecondBrain/` or user-configurable)
- [ ] Port 41932 has no fallback — user gets an error on Tauri startup if taken
- [ ] Optional: macOS Share Extension / Safari extension
