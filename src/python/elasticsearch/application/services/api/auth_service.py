import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict
import logging

from src.python.elasticsearch.config.settings.env_settings import settings
from src.python.elasticsearch.application.repository.mongodb.user_repository import UserRepository
from src.python.elasticsearch.application.repository.mongodb.entities.user_entity import UserEntity, UserRole

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception:
            return False

    def get_password_hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    async def authenticate_user(self, user_id: str, password: str) -> Optional[UserEntity]:
        user = await self.user_repository.find_by_user_id(user_id)
        if not user:
            return None
        if not self.verify_password(password, user.password):
            return None
        return user

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.PyJWTError as e:
            logger.warning(f"Token validation error: {str(e)}")
            return None

    async def initialize_admin_if_not_exists(self):
        """Creates the initial admin user if no users exist."""
        try:
            users_res = await self.user_repository.find_all(limit=1)
            if users_res["total_count"] == 0:
                logger.info("No users found. Creating default admin user.")
                admin_user = UserEntity(
                    user_id="admin",
                    password=self.get_password_hash("admin"),
                    name="Admin",
                    role=UserRole.ADMIN
                )
                await self.user_repository.create(admin_user)
        except Exception as e:
            logger.error(f"Failed to initialize admin: {str(e)}")
