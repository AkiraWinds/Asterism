"""API route for triggering a wiki compile run. See
docs/superpowers/specs/2026-07-31-wiki-compile-layer-design.md. No
in-process scheduler — this endpoint is meant to be invoked externally
(cron/launchd) or via scripts/wiki_compile.py."""

from fastapi import APIRouter, HTTPException

from app.core.config import get_data_root
from app.providers.factory import build_provider
from app.repositories.config_repository import ConfigError, load_config
from app.wiki.compile import run_compile

router = APIRouter(prefix="/wiki", tags=["wiki"])


@router.post("/compile")
def compile_wiki_endpoint():
    data_root = get_data_root()
    try:
        config = load_config(data_root)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    provider = build_provider(config, data_root)
    return run_compile(data_root, provider)
