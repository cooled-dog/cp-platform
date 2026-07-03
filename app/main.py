from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.session import engine, Base
import app.models.models
from app.api.routes import auth

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="CP Platform", lifespan=lifespan)
app.include_router(auth.router)

@app.get("/health")
async def health():
    return {"status": "ok"}