from typing import TypeVar, Generic, Type, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from pymongo import ReturnDocument
from src.python.elasticsearch.application.repository.mongodb.entities.dictionary_base_entity import get_now_utc, get_now_kst_str

T = TypeVar('T', bound=BaseModel)

class BaseMongoRepository(Generic[T]):
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str, model: Type[T], key_field: str):
        self.collection = db[collection_name]
        self.model = model
        self.key_field = key_field

    async def create(self, entity: T) -> T:
        # 가장 높은 index 조회 후 자동 증가
        max_doc = await self.collection.find_one({}, sort=[("index", -1)])
        if max_doc and "index" in max_doc:
            entity.index = max_doc["index"] + 1
        else:
            entity.index = 1

        entity_dict = entity.model_dump()
        await self.collection.insert_one(entity_dict)
        return entity

    async def get_by_key(self, key_value: Any) -> Optional[T]:
        doc = await self.collection.find_one({self.key_field: key_value, "delete_yn": "N"})
        if doc:
            return self.model(**doc)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100, sort_by: str = "index", sort_order: int = -1) -> List[T]:
        cursor = self.collection.find({"delete_yn": "N"}).sort(sort_by, sort_order).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [self.model(**doc) for doc in docs]

    async def search(self, query: dict, skip: int = 0, limit: int = 100, sort_by: str = "index", sort_order: int = -1) -> List[T]:
        query["delete_yn"] = query.get("delete_yn", "N")
        cursor = self.collection.find(query).sort(sort_by, sort_order).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [self.model(**doc) for doc in docs]

    async def count(self, query: dict = None) -> int:
        query = query or {}
        query["delete_yn"] = query.get("delete_yn", "N")
        return await self.collection.count_documents(query)

    async def search_deleted(self, query: dict, skip: int = 0, limit: int = 100, sort_by: str = "index", sort_order: int = -1) -> List[T]:
        query["delete_yn"] = "Y"
        cursor = self.collection.find(query).sort(sort_by, sort_order).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [self.model(**doc) for doc in docs]

    async def count_deleted(self, query: dict = None) -> int:
        query = query or {}
        query["delete_yn"] = "Y"
        return await self.collection.count_documents(query)

    async def update(self, key_value: Any, update_data: dict) -> Optional[T]:
        # 자동으로 현재 시간으로 수정일 갱신
        update_data["updated_at"] = get_now_utc()
        update_data["updated_at_kst"] = get_now_kst_str()
        
        result = await self.collection.find_one_and_update(
            {self.key_field: key_value, "delete_yn": "N"},
            {"$set": update_data},
            return_document=ReturnDocument.AFTER
        )
        if result:
            return self.model(**result)
        return None

    async def delete(self, key_value: Any) -> bool:
        # Soft delete
        update_data = {
            "delete_yn": "Y",
            "updated_at": get_now_utc(),
            "updated_at_kst": get_now_kst_str()
        }
        result = await self.collection.update_one(
            {self.key_field: key_value},
            {"$set": update_data}
        )
        return result.modified_count > 0

    async def get_by_status(self, status: str) -> List[T]:
        cursor = self.collection.find({"delete_yn": "N", "status": status})
        docs = await cursor.to_list(length=None)
        return [self.model(**doc) for doc in docs]

    async def update_status(self, key_value: Any, status: str, applied_at: Any = None, applied_at_kst: str = None) -> bool:
        update_data = {
            "status": status,
            "updated_at": get_now_utc(),
            "updated_at_kst": get_now_kst_str()
        }
        if applied_at:
            update_data["applied_at"] = applied_at
        if applied_at_kst:
            update_data["applied_at_kst"] = applied_at_kst
            
        result = await self.collection.update_one(
            {self.key_field: key_value, "delete_yn": "N"},
            {"$set": update_data}
        )
        return result.modified_count > 0
