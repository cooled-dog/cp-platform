from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.session import engine, Base
import app.models.models   # import so SQLAlchemy sees the models before create_all

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="CP Platform", lifespan=lifespan)

@app.get("/")
async def health():
    return {"status": "ok"}