from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI
from src.python.elasticsearch.config.settings.env_settings import settings

class MongoConnectionManager:
    def __init__(self):
        uri = settings.MONGO_URI
        max_connections = settings.MONGO_MAX_CONNECTIONS
        timeout = settings.MONGO_TIMEOUT

        self.client = AsyncIOMotorClient(
            uri,
            maxPoolSize=max_connections,
            serverSelectionTimeoutMS=timeout
        )
        self.db_name = settings.MONGO_DB_NAME

    def get_client(self) -> AsyncIOMotorClient:
        return self.client

    def get_db(self):
        return self.client[self.db_name]

    async def is_connected(self) -> bool:
        """연결 상태 확인"""
        if not self.client:
            return False

        try:
            # ping 명령어 실행
            await self.client.admin.command('ping')
            return True
        except Exception:
            return False

    async def close(self):
        if self.client:
            self.client.close()

# FastAPI의 전역 객체에 MongoDB 관리 객체를 저장
def init_mongodb_connection(app: FastAPI):
    app.state.mongo_connection_manager = MongoConnectionManager()

def get_mongodb_client(app: FastAPI) -> AsyncIOMotorClient:
    return app.state.mongo_connection_manager.get_client()

def get_mongodb_database(app: FastAPI):
    return app.state.mongo_connection_manager.get_db()

async def close_mongodb_connection(app: FastAPI):
    if hasattr(app.state, "mongo_connection_manager"):
        await app.state.mongo_connection_manager.close()

async def is_mongodb_connected(app: FastAPI) -> bool:
    """MongoDB 연결 상태 확인"""
    if hasattr(app.state, "mongo_connection_manager"):
        return await app.state.mongo_connection_manager.is_connected()
    return False
