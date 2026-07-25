from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.sources import router as sources_router

app = FastAPI(title="Asterism Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
