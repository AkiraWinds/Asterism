from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.agent import router as agent_router
from app.routers.graph import router as graph_router
from app.routers.radar import router as radar_router
from app.routers.sources import router as sources_router
from app.routers.watchlist import router as watchlist_router
from app.routers.wiki import router as wiki_router

app = FastAPI(title="Asterism Backend")

app.add_middleware(
    CORSMiddleware,
    # Both loopback spellings are allowed: some clients' DNS resolution
    # tries ::1 before 127.0.0.1 and doesn't fall back to IPv4 on a refused
    # IPv6 connection (the frontend service only binds 127.0.0.1), so users
    # sometimes load the frontend via the literal 127.0.0.1 origin instead
    # of localhost. Both are still loopback-only — no broader exposure.
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources_router)
app.include_router(agent_router)
app.include_router(graph_router)
app.include_router(radar_router)
app.include_router(watchlist_router)
app.include_router(wiki_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
