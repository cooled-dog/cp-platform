from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class TestCaseIn(BaseModel):
    input_data: str
    expected_output: str
    is_sample: bool = False

class TestCaseOut(BaseModel):
    id: int
    input_data: str
    expected_output: str
    is_sample: bool
    model_config = {"from_attributes": True}

class ProblemCreate(BaseModel):
    title: str
    description: str
    time_limit_ms: int = 2000
    memory_limit_mb: int = 256
    test_cases: list[TestCaseIn]

class ProblemOut(BaseModel):
    id: int
    title: str
    description: str
    time_limit_ms: int
    memory_limit_mb: int
    created_at: datetime
    sample_test_cases: list[TestCaseOut] = []
    model_config = {"from_attributes": True}

class ProblemListItem(BaseModel):
    id: int
    title: str
    time_limit_ms: int
    memory_limit_mb: int
    model_config = {"from_attributes": True}