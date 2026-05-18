from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from src.python.elasticsearch.application.schemas.requests.auth_request import (
    LoginRequest, UserCreateRequest, UserUpdateRequest, AdminUserUpdateRequest
)
from src.python.elasticsearch.application.schemas.responses.auth_response import TokenResponse, UserResponse
from src.python.elasticsearch.application.services.api.auth_service import AuthService
from src.python.elasticsearch.application.repository.mongodb.user_repository import UserRepository
from src.python.elasticsearch.application.repository.mongodb.entities.user_entity import UserEntity, UserRole

logger = logging.getLogger(__name__)

auth_endpoint = APIRouter()
security = HTTPBearer()

def get_auth_service(request: Request) -> AuthService:
    # Get MongoDB manager from app state
    manager = request.app.state.mongo_connection_manager
    repo = UserRepository(manager)
    return AuthService(repo)

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
) -> UserResponse:
    token = credentials.credentials
    payload = auth_service.decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    repo = auth_service.user_repository
    user = await repo.find_by_user_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return UserResponse(
        user_id=user.user_id,
        name=user.name,
        role=user.role,
        created_at_kst=user.created_at_kst,
        updated_at_kst=user.updated_at_kst
    )

async def get_current_user_sse(
    request: Request,
    token: str = None,
    auth_service: AuthService = Depends(get_auth_service)
) -> UserResponse:
    # Try query param 'token' first
    token = token or request.query_params.get("token")
    if not token:
        # Fallback to Authorization header if present
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing or invalid",
        )
        
    payload = auth_service.decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    repo = auth_service.user_repository
    user = await repo.find_by_user_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return UserResponse(
        user_id=user.user_id,
        name=user.name,
        role=user.role,
        created_at_kst=user.created_at_kst,
        updated_at_kst=user.updated_at_kst
    )

async def require_admin_sse(
    current_user: UserResponse = Depends(get_current_user_sse)
) -> UserResponse:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ADMIN can access this stream"
        )
    return current_user

# ==========================================
# Login
# ==========================================
@auth_endpoint.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, auth_service: AuthService = Depends(get_auth_service)):
    user = await auth_service.authenticate_user(req.user_id, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect user ID or password"
        )
    
    token = auth_service.create_access_token(data={"sub": user.user_id, "role": user.role})
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.user_id,
        name=user.name,
        role=user.role
    )

# ==========================================
# Current User
# ==========================================
@auth_endpoint.get("/me", response_model=UserResponse)
async def read_users_me(current_user: UserResponse = Depends(get_current_user)):
    return current_user

# ==========================================
# User Management (ADMIN only unless self-update)
# ==========================================
@auth_endpoint.post("/users", response_model=UserResponse)
async def create_user(
    req: UserCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Create a new user. ADMIN only."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only ADMIN can create users")
    
    repo = auth_service.user_repository
    existing = await repo.find_by_user_id(req.user_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")
    
    new_user = UserEntity(
        user_id=req.user_id,
        password=auth_service.get_password_hash(req.password),
        name=req.name,
        role=req.role
    )
    await repo.create(new_user)
    
    return UserResponse(
        user_id=new_user.user_id,
        name=new_user.name,
        role=new_user.role,
        created_at_kst=new_user.created_at_kst,
        updated_at_kst=new_user.updated_at_kst
    )

@auth_endpoint.get("/users")
async def get_users(
    skip: int = 0,
    limit: int = 100,
    current_user: UserResponse = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """List all users. ADMIN only."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only ADMIN can view user list")
    return await auth_service.user_repository.find_all(skip=skip, limit=limit)

@auth_endpoint.put("/users/me")
async def update_my_profile(
    req: UserUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Update own profile (name, password). Any authenticated user."""
    update_data = {}
    if req.name is not None:
        update_data["name"] = req.name
    if req.password is not None:
        update_data["password"] = auth_service.get_password_hash(req.password)
    
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    
    updated = await auth_service.user_repository.update(current_user.user_id, update_data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    return UserResponse(
        user_id=updated.user_id,
        name=updated.name,
        role=updated.role,
        created_at_kst=updated.created_at_kst,
        updated_at_kst=updated.updated_at_kst
    )

@auth_endpoint.put("/users/{user_id}")
async def admin_update_user(
    user_id: str,
    req: AdminUserUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Update any user's profile. ADMIN only."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only ADMIN can update other users")
    
    update_data = {}
    if req.name is not None:
        update_data["name"] = req.name
    if req.password is not None:
        update_data["password"] = auth_service.get_password_hash(req.password)
    if req.role is not None:
        update_data["role"] = req.role.value
    
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    
    updated = await auth_service.user_repository.update(user_id, update_data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    return UserResponse(
        user_id=updated.user_id,
        name=updated.name,
        role=updated.role,
        created_at_kst=updated.created_at_kst,
        updated_at_kst=updated.updated_at_kst
    )

@auth_endpoint.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: UserResponse = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Soft-delete a user. ADMIN only. Cannot delete yourself."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only ADMIN can delete users")
    
    if current_user.user_id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")
    
    success = await auth_service.user_repository.delete(user_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    return {"success": True, "message": f"User '{user_id}' has been deleted"}
