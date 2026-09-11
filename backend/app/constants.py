"""Small tuning constants shared across otherwise-unrelated modules. Lives
here (rather than config.json) because these are algorithm knobs, not
per-deployment/per-user settings — they don't vary across environments and
aren't secrets, so putting them in the user-facing config file would just
invite silent behavior drift with none of the reasoning here alongside it.
Compare config_repository.py, which holds the actual per-deployment
settings (provider credentials, embeddings model/key).
"""

# Retry budget for an LLM call that must return parseable/valid JSON, used by
# every "_complete_with_retry"-shaped helper in the codebase (analysis,
# concept graph dedup, radar judge). Was previously defined three times with
# the same value and no import relationship between the copies — drifting
# out of sync was possible with nothing to catch it.
MAX_ATTEMPTS = 2
