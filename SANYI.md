# SANYI.md — change contract

project: Asterism
version: 1
last-audit: 2026-08-19

## 不易 Buyi

### Data-root boundary

<!-- CLAUDE.md principle #3 ("Security boundary: all operations stay within
     $ASTERISM_DATA_ROOT"). Implemented deterministically via resolve() +
     is_relative_to() checks in source_repository.py, not just a convention. -->

- paths: backend/app/repositories/source_repository.py, backend/app/core/config.py
- contract: Every filesystem read/write derived from a source_id, chat_id, or
  other user-controlled path segment must be resolved and checked with
  `is_relative_to()` against the data root (or the relevant subdirectory)
  before use. Must not be bypassable via any config, env var, or flag.
- evidence: backend/tests/test_source_repository.py::test_get_source_rejects_path_traversal

### SSRF guard on outbound fetches

<!-- Prevents the server being tricked into requesting internal/private
     network addresses (cloud metadata endpoints, localhost services) via a
     user-supplied source or feed URL. -->

- paths: backend/app/ingestion/fetcher.py, backend/app/radar/fetcher.py
- contract: Any outbound HTTP fetch triggered by a user-supplied URL (source
  capture, radar feed fetch) must reject targets that resolve to a private/
  non-public IP address, and must re-check this on every redirect hop, not
  just the input URL. Must not be bypassable via any config, env var, or flag.
- evidence: backend/tests/test_ingestion_fetcher.py::test_fetch_url_blocks_redirect_chain_landing_on_private_ip,
  backend/tests/test_ingestion_fetcher.py::test_fetch_url_blocks_direct_request_to_non_public_ip

### Provider credential / secret handling

<!-- Leaking API keys or user content into logs is a trust/financial failure
     (leaked keys are billable and revocable-but-damaging; leaked content
     breaks the local-first privacy promise). -->

- paths: backend/app/repositories/config_repository.py, backend/app/providers/
- contract: `api_key`, `embeddings_api_key`, and `brave_api_key` must never be
  written to logs or debug output. (Note: unlike the legacy stack, this
  rewrite currently has no opt-in debug-log mechanism for full agent
  prompts/responses at all — if one is added, it must default off and be
  recorded as a Bianyi-configured, Buyi-guarded gate, not unconditional.)
- evidence: backend/tests/test_config_repository.py::test_agent_config_repr_never_includes_the_api_key

## 简易 Jianyi

### AnalysisState / SystemState

<!-- The two TypedDicts that flow through the analysis and system LangGraph
     graphs. Growth here is the main entropy risk for the analysis pipeline. -->

- paths: backend/app/analysis/state.py, backend/app/state.py
- budget: ≤ 15 fields combined; each new field needs justification in the PR
- current: AnalysisState 11 fields + SystemState 6 fields (2 shared) = 15 (2026-08-19)

### AnalysisResult and its sub-models

<!-- The shape of analysis.json — Triage/Digest/Critique/Claim/Connection.
     Each *_error field is an intentional partial-failure carrier, not
     entropy; new content fields still need justification. -->

- paths: backend/app/schemas/analysis.py
- budget: AnalysisResult ≤ 12 top-level fields; each new field needs
  justification in the PR
- current: 11 fields (2026-08-19)

### Analysis execution graph

<!-- The LangGraph fan-out/fan-in wiring for the 4 parallel analysis nodes.
     For agent systems the graph is usually the dominant complexity source. -->

- paths: backend/app/analysis/graph.py, backend/app/graph.py
- budget: new nodes/edges/branches/cycles need justification in the PR
  (qualitative — no fixed numeric ceiling)
- current: analysis graph = 6 nodes / 9 edges (4-way fan-out + fan-in, no
  conditional routing); system graph = 1 node wrapping the subgraph (2026-08-19)

### Provider abstraction interface

<!-- The single Provider interface all 4 implementations must satisfy
     (base.py). Keeps provider-specific protocol details out of core code. -->

- paths: backend/app/providers/base.py
- budget: interface methods should stay minimal; new methods need
  justification and must be implementable by all 4 providers (cli_claude,
  cli_codex, api_anthropic, api_openai)
- current: 2 methods (complete, stream_complete) (2026-08-19)

## 变易 Bianyi

### Analysis / chat / concept-graph / wiki prompts

<!-- Matches the repo's existing convention: one prompts.py per module. -->

- paths: backend/app/analysis/prompts.py, backend/app/chat/prompts.py,
  backend/app/concept_graph/prompts.py, backend/app/wiki/prompts.py
- contract: All prompt text for that module lives in its prompts.py; inline
  prompt strings elsewhere (nodes.py, pipeline.py, routers) are violations.

### Provider/strategy config

<!-- config.json's strategy/provider selection and validation rules. -->

- paths: backend/app/repositories/config_repository.py#CLI_PROVIDERS,
  backend/app/repositories/config_repository.py#API_KEY_PROVIDERS,
  backend/app/repositories/config_repository.py#STRATEGIES
- contract: The set of valid providers/strategies lives only here; a
  hardcoded provider-name check or strategy string elsewhere is a violation.

### Data root location

- paths: backend/app/core/config.py#get_data_root
- contract: `ASTERISM_DATA_ROOT` resolution logic lives only here; other
  code must call `get_data_root()` rather than reading the env var or
  hardcoding a default path directly.

## Migrations

<!-- Empty at init; fills as layers are promoted/demoted. -->

## Pending

- Immutability of `meta.json` / `original.*` after capture (CLAUDE.md
  principle #4: "Originals are immutable"). Parked at init — disputed
  whether this should be a code-enforced Buyi invariant (no code guard
  currently forbids overwriting these files; the "NEVER" in the reanalyze
  workflow docs is currently a convention, not deterministic code) or
  formalized differently. Enforced as Buyi (strictest) until resolved.

## Debt

<!-- All three Buyi entries now have evidence tests as of the closing audit
     (2026-08-19); nothing outstanding here at init. -->
