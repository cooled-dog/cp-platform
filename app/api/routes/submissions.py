from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.models import Submission, Problem, User, Verdict
from app.schemas.schemas import SubmissionCreate, SubmissionOut
from app.services.rate_limiter import check_rate_limit, seconds_until_retry
from app.workers.judge_worker import enqueue

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionOut, status_code=202)
async def create_submission(
    payload: SubmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not check_rate_limit(current_user.id):
        retry = seconds_until_retry(current_user.id)
        raise HTTPException(
            status_code=429,
            detail=f"Too many submissions. Try again in {retry}s.",
            headers={"Retry-After": str(retry)},
        )

    result = await db.execute(select(Problem).where(Problem.id == payload.problem_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Problem not found")

    submission = Submission(
        user_id=current_user.id,
        problem_id=payload.problem_id,
        code=payload.code,
        language=payload.language,
        status=Verdict.PENDING,
    )
    db.add(submission)
    await db.flush()
    await db.refresh(submission)
    await enqueue(submission.id)
    return submission


@router.get("/{submission_id}", response_model=SubmissionOut)
async def get_submission(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    return submission


@router.get("", response_model=list[SubmissionOut])
async def list_my_submissions(
    problem_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Submission).where(Submission.user_id == current_user.id)
    if problem_id:
        query = query.where(Submission.problem_id == problem_id)
    query = query.order_by(Submission.submitted_at.desc()).limit(50)
    result = await db.execute(query)
    return result.scalars().all()