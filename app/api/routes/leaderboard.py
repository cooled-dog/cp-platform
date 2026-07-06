from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from app.db.session import get_db
from app.models.models import Submission, User, Verdict
from app.schemas.schemas import LeaderboardEntry

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("", response_model=list[LeaderboardEntry])
async def get_leaderboard(db: AsyncSession = Depends(get_db)):
    query = (
        select(
            User.id.label("user_id"),
            User.username.label("username"),
            func.count(func.distinct(
                case((Submission.verdict == Verdict.AC, Submission.problem_id))
            )).label("problems_solved"),
            func.coalesce(
                func.sum(
                    case((Submission.verdict == Verdict.AC, Submission.time_ms), else_=0)
                ), 0
            ).label("total_penalty_ms"),
        )
        .join(Submission, Submission.user_id == User.id)
        .group_by(User.id, User.username)
        .order_by(
            func.count(func.distinct(
                case((Submission.verdict == Verdict.AC, Submission.problem_id))
            )).desc(),
            func.coalesce(
                func.sum(
                    case((Submission.verdict == Verdict.AC, Submission.time_ms), else_=0)
                ), 0
            ).asc(),
        )
    )
    result = await db.execute(query)
    rows = result.all()
    return [
        LeaderboardEntry(
            user_id=r.user_id,
            username=r.username,
            problems_solved=r.problems_solved,
            total_penalty_ms=r.total_penalty_ms,
        )
        for r in rows
    ]