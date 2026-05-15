from fastapi import Depends, HTTPException, status
from src.python.elasticsearch.application.endpoints.auth_endpoint import get_current_user
from src.python.elasticsearch.application.schemas.responses.auth_response import UserResponse
from src.python.elasticsearch.common.enums.user_role import UserRole


def require_role(*allowed_roles: UserRole):
    """FastAPI dependency that checks if the current user has one of the allowed roles.

    Usage:
        @router.post("/something")
        async def handler(current_user = Depends(require_role(UserRole.ADMIN, UserRole.WRITER))):
            ...
    """
    async def role_checker(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        if current_user.role not in [r.value for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {[r.value for r in allowed_roles]}"
            )
        return current_user
    return role_checker
