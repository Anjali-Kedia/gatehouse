from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers.evaluations import router as evaluations_router
from gatehouse.config import settings
from gatehouse.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Gatehouse", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,  # required for the session cookie to survive a cross-origin dev setup
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(evaluations_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "jev_adapter": settings.jev_adapter}
