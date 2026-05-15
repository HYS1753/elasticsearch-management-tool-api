from motor.motor_asyncio import AsyncIOMotorDatabase
from src.python.elasticsearch.application.repository.mongodb.base_mongo_repository import BaseMongoRepository
from src.python.elasticsearch.application.repository.mongodb.entities.correction_dictionary_entity import CorrectionDictionaryEntity

class CorrectionDictionaryRepository(BaseMongoRepository[CorrectionDictionaryEntity]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(
            db=db,
            collection_name="correction_dictionary",
            model=CorrectionDictionaryEntity,
            key_field="incorrect"
        )

    async def search_by_keyword(self, keyword: str, skip: int = 0, limit: int = 100, sort_by: str = "index", sort_order: int = -1) -> tuple[int, list[CorrectionDictionaryEntity]]:
        query = {
            "$or": [
                {"incorrect": {"$regex": keyword, "$options": "i"}},
                {"corrected": {"$regex": keyword, "$options": "i"}}
            ]
        } if keyword else {}
        total_count = await self.count(query)
        items = await self.search(query, skip, limit, sort_by, sort_order)
        return total_count, items

    async def admin_search_deleted_by_keyword(self, keyword: str, skip: int = 0, limit: int = 100, sort_by: str = "index", sort_order: int = -1) -> tuple[int, list[CorrectionDictionaryEntity]]:
        query = {
            "$or": [
                {"incorrect": {"$regex": keyword, "$options": "i"}},
                {"corrected": {"$regex": keyword, "$options": "i"}}
            ]
        } if keyword else {}
        total_count = await self.count_deleted(query)
        items = await self.search_deleted(query, skip, limit, sort_by, sort_order)
        return total_count, items
