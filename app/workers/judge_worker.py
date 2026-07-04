import asyncio
import logging
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.models import Submission, Problem, TestCase, Verdict
from app.services.judge import judge_submission

logger = logging.getLogger(__name__)

submission_queue: asyncio.Queue[int] = asyncio.Queue()


async def enqueue(submission_id: int) -> None:
    await submission_queue.put(submission_id)


async def _process(submission_id: int) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Submission).where(Submission.id == submission_id))
        submission = result.scalar_one_or_none()
        if not submission:
            logger.error(f"Submission {submission_id} not found")
            return

        submission.status = Verdict.RUNNING
        await db.commit()

        result = await db.execute(select(Problem).where(Problem.id == submission.problem_id))
        problem = result.scalar_one_or_none()
        if not problem:
            submission.verdict = Verdict.RE
            submission.status = Verdict.RE
            await db.commit()
            return

        result = await db.execute(
            select(TestCase).where(TestCase.problem_id == problem.id)
        )
        test_cases = [(tc.input_data, tc.expected_output) for tc in result.scalars().all()]

        try:
            result = await judge_submission(
                code=submission.code,
                language=submission.language,
                test_cases=test_cases,
                time_limit_ms=problem.time_limit_ms,
                memory_limit_mb=problem.memory_limit_mb,
            )
            submission.verdict = result.verdict
            submission.status  = result.verdict
            submission.time_ms = result.time_ms
        except Exception as e:
            logger.exception(f"Judge crashed on submission {submission_id}: {e}")
            submission.verdict = Verdict.RE
            submission.status  = Verdict.RE

        await db.commit()
        logger.info(f"Submission {submission_id} → {submission.verdict}")


async def worker(worker_id: int) -> None:
    logger.info(f"Worker {worker_id} started")
    while True:
        submission_id = await submission_queue.get()
        try:
            await _process(submission_id)
        except Exception as e:
            logger.exception(f"Worker {worker_id} unhandled error: {e}")
        finally:
            submission_queue.task_done()


async def start_workers(n: int = 2) -> None:
    for i in range(n):
        asyncio.create_task(worker(i))
    logger.info(f"Started {n} judge workers")