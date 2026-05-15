from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone, timedelta
from src.python.elasticsearch.common.enums.user_role import UserRole

KST = timezone(timedelta(hours=9))

def get_now_utc() -> datetime:
    return datetime.now(timezone.utc)

def get_now_kst_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

class UserEntity(BaseModel):
    user_id: str
    password: str
    name: str
    role: UserRole = UserRole.VIEWER
    delete_yn: str = "N"
    created_at: datetime = Field(default_factory=get_now_utc)
    created_at_kst: str = Field(default_factory=get_now_kst_str)
    updated_at: datetime = Field(default_factory=get_now_utc)
    updated_at_kst: str = Field(default_factory=get_now_kst_str)
