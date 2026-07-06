from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import select
from app.db.session import engine, Base, AsyncSessionLocal
import app.models.models
from app.models.models import Submission, Verdict
from app.api.routes import auth, problems, submissions, leaderboard
from app.workers.judge_worker import enqueue, start_workers

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await start_workers()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Submission.id).where(Submission.status.in_([Verdict.PENDING, Verdict.RUNNING]))
        )
        orphaned_ids = [row[0] for row in result.all()]
        for sub_id in orphaned_ids:
            await enqueue(sub_id)
        if orphaned_ids:
            print(f"Re-enqueued {len(orphaned_ids)} orphaned submissions: {orphaned_ids}")

    yield
    await engine.dispose()

app = FastAPI(title="CP Platform", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(problems.router)
app.include_router(submissions.router)
app.include_router(leaderboard.router)

@app.get("/health")
async def health():
    return {"status": "ok"}