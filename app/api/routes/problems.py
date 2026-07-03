from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.api.deps import get_current_user, get_admin_user
from app.db.session import get_db
from app.models.models import Problem, TestCase, User
from app.schemas.schemas import ProblemCreate, ProblemOut, ProblemListItem, TestCaseOut

router = APIRouter(prefix="/problems", tags=["problems"])


@router.post("", response_model=ProblemOut, status_code=201)
async def create_problem(
    payload: ProblemCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    if not payload.test_cases:
        raise HTTPException(status_code=400, detail="At least one test case required")

    problem = Problem(
        title=payload.title,
        description=payload.description,
        time_limit_ms=payload.time_limit_ms,
        memory_limit_mb=payload.memory_limit_mb,
        created_by=admin.id,
    )
    db.add(problem)
    await db.flush()

    for tc in payload.test_cases:
        db.add(TestCase(
            problem_id=problem.id,
            input_data=tc.input_data,
            expected_output=tc.expected_output,
            is_sample=tc.is_sample,
        ))

    await db.flush()

    result = await db.execute(
        select(Problem)
        .options(selectinload(Problem.test_cases))
        .where(Problem.id == problem.id)
    )
    problem = result.scalar_one()
    return _to_problem_out(problem)


@router.get("", response_model=list[ProblemListItem])
async def list_problems(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Problem).order_by(Problem.id))
    return result.scalars().all()


@router.get("/{problem_id}", response_model=ProblemOut)
async def get_problem(problem_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Problem)
        .options(selectinload(Problem.test_cases))
        .where(Problem.id == problem_id)
    )
    problem = result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return _to_problem_out(problem)


@router.delete("/{problem_id}", status_code=204)
async def delete_problem(
    problem_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    result = await db.execute(select(Problem).where(Problem.id == problem_id))
    problem = result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    await db.delete(problem)


def _to_problem_out(problem: Problem) -> ProblemOut:
    samples = [
        TestCaseOut(
            id=tc.id,
            input_data=tc.input_data,
            expected_output=tc.expected_output,
            is_sample=tc.is_sample,
        )
        for tc in problem.test_cases if tc.is_sample
    ]
    return ProblemOut(
        id=problem.id,
        title=problem.title,
        description=problem.description,
        time_limit_ms=problem.time_limit_ms,
        memory_limit_mb=problem.memory_limit_mb,
        created_at=problem.created_at,
        sample_test_cases=samples,
    )