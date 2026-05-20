import logging
from typing import Optional, List, Dict, Any
from src.python.elasticsearch.config.connections.mongodb_connection_manager import MongoConnectionManager
from src.python.elasticsearch.application.repository.mongodb.entities.user_entity import UserEntity

logger = logging.getLogger(__name__)

class UserRepository:
    def __init__(self, connection_manager: MongoConnectionManager):
        self.connection_manager = connection_manager
        self.collection_name = "users"

    def get_collection(self):
        db = self.connection_manager.get_db()
        return db[self.collection_name]

    async def find_by_user_id(self, user_id: str, include_deleted: bool = False) -> Optional[UserEntity]:
        try:
            collection = self.get_collection()
            query = {"user_id": user_id}
            if not include_deleted:
                query["delete_yn"] = "N"

            doc = await collection.find_one(query)
            if not doc:
                return None
            return UserEntity(**doc)
        except Exception as e:
            logger.error(f"Error finding user by id {user_id}: {str(e)}")
            raise

    async def find_all(self, skip: int = 0, limit: int = 10, include_deleted: bool = False) -> Dict[str, Any]:
        try:
            collection = self.get_collection()
            query = {}
            if not include_deleted:
                query["delete_yn"] = "N"

            total = await collection.count_documents(query)
            cursor = collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
            
            items = []
            async for doc in cursor:
                doc_copy = dict(doc)
                if "_id" in doc_copy:
                    doc_copy["_id"] = str(doc_copy["_id"])
                
                # Exclude password in find_all
                if "password" in doc_copy:
                    del doc_copy["password"]
                items.append(doc_copy)

            return {
                "total_count": total,
                "items": items
            }
        except Exception as e:
            logger.error(f"Error finding all users: {str(e)}")
            raise

    async def create(self, entity: UserEntity) -> UserEntity:
        try:
            collection = self.get_collection()
            doc = entity.model_dump()
            await collection.insert_one(doc)
            return entity
        except Exception as e:
            logger.error(f"Error creating user {entity.user_id}: {str(e)}")
            raise

    async def update(self, user_id: str, update_data: Dict[str, Any]) -> Optional[UserEntity]:
        from src.python.elasticsearch.application.repository.mongodb.entities.user_entity import get_now_utc, get_now_kst_str
        try:
            collection = self.get_collection()
            update_data["updated_at"] = get_now_utc()
            update_data["updated_at_kst"] = get_now_kst_str()

            result = await collection.find_one_and_update(
                {"user_id": user_id},
                {"$set": update_data},
                return_document=True
            )
            if not result:
                return None
            return UserEntity(**result)
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {str(e)}")
            raise

    async def delete(self, user_id: str) -> bool:
        from src.python.elasticsearch.application.repository.mongodb.entities.user_entity import get_now_utc, get_now_kst_str
        try:
            collection = self.get_collection()
            result = await collection.update_one(
                {"user_id": user_id},
                {"$set": {
                    "delete_yn": "Y",
                    "updated_at": get_now_utc(),
                    "updated_at_kst": get_now_kst_str()
                }}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {str(e)}")
            raise
