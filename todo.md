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
- **URL ingestion — no SSRF guard beyond the login-host check**: `http://169.254.169.254/...` and `http://localhost:8000`
  pass through `fetch_url` untouched. Low severity given the single-user/local-first threat model; revisit if ingestion is
  ever exposed to untrusted multi-tenant use.
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
