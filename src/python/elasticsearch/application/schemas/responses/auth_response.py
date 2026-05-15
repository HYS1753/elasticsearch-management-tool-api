from pydantic import BaseModel
from typing import Optional

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    role: str

class UserResponse(BaseModel):
    user_id: str
    name: str
    role: str
    created_at_kst: str
    updated_at_kst: str
