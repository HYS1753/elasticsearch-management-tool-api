from pydantic import BaseModel
from typing import Optional
from src.python.elasticsearch.common.enums.user_role import UserRole

class LoginRequest(BaseModel):
    user_id: str
    password: str

class UserCreateRequest(BaseModel):
    user_id: str
    password: str
    name: str
    role: UserRole = UserRole.VIEWER

class UserUpdateRequest(BaseModel):
    """For self-update: users can change their own name and password."""
    name: Optional[str] = None
    password: Optional[str] = None

class AdminUserUpdateRequest(BaseModel):
    """For admin-update: admin can change name, password, and role."""
    name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None

