from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class Verdict(str, PyEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    AC      = "AC"    # Accepted
    WA      = "WA"    # Wrong Answer
    TLE     = "TLE"   # Time Limit Exceeded
    MLE     = "MLE"   # Memory Limit Exceeded
    RE      = "RE"    # Runtime Error
    CE      = "CE"    # Compilation Error


class Language(str, PyEnum):
    CPP    = "cpp"
    PYTHON = "python"
    JAVA   = "java"


class User(Base):
    __tablename__ = "users"

    id:            Mapped[int]      = mapped_column(Integer, primary_key=True)
    username:      Mapped[str]      = mapped_column(String(50), unique=True, nullable=False)
    email:         Mapped[str]      = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str]      = mapped_column(String(255), nullable=False)
    is_admin:      Mapped[bool]     = mapped_column(Boolean, default=False)
    created_at:    Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    submissions: Mapped[list["Submission"]] = relationship(back_populates="user")


class Problem(Base):
    __tablename__ = "problems"

    id:              Mapped[int]      = mapped_column(Integer, primary_key=True)
    title:           Mapped[str]      = mapped_column(String(255), nullable=False)
    description:     Mapped[str]      = mapped_column(Text, nullable=False)
    time_limit_ms:   Mapped[int]      = mapped_column(Integer, default=2000)
    memory_limit_mb: Mapped[int]      = mapped_column(Integer, default=256)
    created_by:      Mapped[int]      = mapped_column(ForeignKey("users.id"))
    created_at:      Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    test_cases:  Mapped[list["TestCase"]]   = relationship(back_populates="problem", cascade="all, delete-orphan")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="problem")


class TestCase(Base):
    __tablename__ = "test_cases"

    id:              Mapped[int]  = mapped_column(Integer, primary_key=True)
    problem_id:      Mapped[int]  = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    input_data:      Mapped[str]  = mapped_column(Text, nullable=False)
    expected_output: Mapped[str]  = mapped_column(Text, nullable=False)
    is_sample:       Mapped[bool] = mapped_column(Boolean, default=False)

    problem: Mapped["Problem"] = relationship(back_populates="test_cases")


class Submission(Base):
    __tablename__ = "submissions"

    id:           Mapped[int]      = mapped_column(Integer, primary_key=True)
    user_id:      Mapped[int]      = mapped_column(ForeignKey("users.id"))
    problem_id:   Mapped[int]      = mapped_column(ForeignKey("problems.id"))
    code:         Mapped[str]      = mapped_column(Text, nullable=False)
    language:     Mapped[str]      = mapped_column(Enum(Language), nullable=False)
    status:       Mapped[str]      = mapped_column(Enum(Verdict), default=Verdict.PENDING)
    verdict:      Mapped[str]      = mapped_column(Enum(Verdict), nullable=True)
    time_ms:      Mapped[int]      = mapped_column(Integer, nullable=True)
    memory_kb:    Mapped[int]      = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user:    Mapped["User"]    = relationship(back_populates="submissions")
    problem: Mapped["Problem"] = relationship(back_populates="submissions")
    