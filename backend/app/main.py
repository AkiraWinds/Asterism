from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.agent import router as agent_router
from app.routers.graph import router as graph_router
from app.routers.sources import router as sources_router

app = FastAPI(title="Asterism Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources_router)
app.include_router(agent_router)
app.include_router(graph_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
