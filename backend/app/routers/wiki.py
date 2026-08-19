"""API routes for triggering a wiki compile run and reading already-compiled
wiki pages. See docs/superpowers/specs/2026-07-31-wiki-compile-layer-design.md
and docs/superpowers/specs/2026-08-19-graph-wiki-panel-design.md. No
in-process scheduler for compilation — that endpoint is meant to be invoked
externally (cron/launchd) or via scripts/wiki_compile.py; the read routes
below are plain synchronous file reads, safe to call anytime."""

from fastapi import APIRouter, HTTPException

from app.core.config import get_data_root
from app.providers.factory import build_provider
from app.repositories.config_repository import ConfigError, load_config
from app.schemas.wiki import WikiPageResponse
from app.wiki.compile import run_compile
from app.wiki.store_reader import get_wiki_page_by_concept_id, get_wiki_page_by_slug

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


@router.get("/pages/by-slug/{slug}", response_model=WikiPageResponse)
def get_wiki_page_by_slug_endpoint(slug: str) -> WikiPageResponse:
    # Registered before /pages/{concept_id} so FastAPI's path-matching
    # doesn't treat the literal segment "by-slug" as a concept_id value.
    data_root = get_data_root()
    page = get_wiki_page_by_slug(data_root / "wiki", slug)
    if page is None:
        raise HTTPException(status_code=404, detail="No wiki page for this slug")
    return WikiPageResponse(**page)


@router.get("/pages/{concept_id}", response_model=WikiPageResponse)
def get_wiki_page_by_concept_id_endpoint(concept_id: str) -> WikiPageResponse:
    data_root = get_data_root()
    page = get_wiki_page_by_concept_id(data_root / "wiki", concept_id)
    if page is None:
        raise HTTPException(status_code=404, detail="No wiki page for this concept")
    return WikiPageResponse(**page)
