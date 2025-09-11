from pydantic import BaseModel
from typing import Optional


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class UserLogin(BaseModel):
    registro: str
    password: str


class TaskResponse(BaseModel):
    task_id: str
    message: str
    status: str = "pending"


class TaskStatus(BaseModel):
    id: str
    status: str
    type: str
    result: Optional[str] = None
    error: Optional[str] = None
