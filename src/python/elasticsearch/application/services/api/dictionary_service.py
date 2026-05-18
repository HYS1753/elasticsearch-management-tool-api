from motor.motor_asyncio import AsyncIOMotorDatabase
from src.python.elasticsearch.application.repository.mongodb.user_dictionary_repository import UserDictionaryRepository
from src.python.elasticsearch.application.repository.mongodb.decompound_dictionary_repository import DecompoundDictionaryRepository
from src.python.elasticsearch.application.repository.mongodb.synonym_dictionary_repository import SynonymDictionaryRepository
from src.python.elasticsearch.application.repository.mongodb.correction_dictionary_repository import CorrectionDictionaryRepository
from src.python.elasticsearch.application.repository.mongodb.stopword_dictionary_repository import StopwordDictionaryRepository

from src.python.elasticsearch.application.schemas.requests.dictionary.dictionary_req import (
    UserDictionaryCreateReq, UserDictionaryUpdateReq,
    DecompoundDictionaryCreateReq, DecompoundDictionaryUpdateReq,
    SynonymDictionaryCreateReq, SynonymDictionaryUpdateReq,
    CorrectionDictionaryCreateReq, CorrectionDictionaryUpdateReq,
    StopwordDictionaryCreateReq, StopwordDictionaryUpdateReq
)

from src.python.elasticsearch.application.repository.mongodb.entities.user_dictionary_entity import UserDictionaryEntity
from src.python.elasticsearch.application.repository.mongodb.entities.decompound_dictionary_entity import DecompoundDictionaryEntity
from src.python.elasticsearch.application.repository.mongodb.entities.synonym_dictionary_entity import SynonymDictionaryEntity
from src.python.elasticsearch.application.repository.mongodb.entities.correction_dictionary_entity import CorrectionDictionaryEntity
from src.python.elasticsearch.application.repository.mongodb.entities.stopword_dictionary_entity import StopwordDictionaryEntity
from src.python.elasticsearch.common.enums.dictionary_status import DictionaryStatus


class UserDictionaryService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = UserDictionaryRepository(db)

    async def get_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.search_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def get_admin_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.admin_search_deleted_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def create(self, req: UserDictionaryCreateReq):
        entity = UserDictionaryEntity(**req.model_dump())
        return await self.repo.create(entity)

    async def update(self, word: str, req: UserDictionaryUpdateReq):
        update_data = req.model_dump(exclude_unset=True)
        if "status" not in update_data:
            update_data["status"] = DictionaryStatus.DRAFT
        return await self.repo.update(word, update_data)

    async def delete(self, word: str):
        return await self.repo.delete(word)


class DecompoundDictionaryService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = DecompoundDictionaryRepository(db)

    async def get_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.search_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def get_admin_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.admin_search_deleted_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def create(self, req: DecompoundDictionaryCreateReq):
        entity = DecompoundDictionaryEntity(**req.model_dump())
        return await self.repo.create(entity)

    async def update(self, compound_word: str, req: DecompoundDictionaryUpdateReq):
        update_data = req.model_dump(exclude_unset=True)
        if "status" not in update_data:
            update_data["status"] = DictionaryStatus.DRAFT
        return await self.repo.update(compound_word, update_data)

    async def delete(self, compound_word: str):
        return await self.repo.delete(compound_word)


class SynonymDictionaryService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = SynonymDictionaryRepository(db)

    async def get_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.search_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def get_admin_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.admin_search_deleted_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def create(self, req: SynonymDictionaryCreateReq):
        # synonyms는 List이므로, 리스트 자체를 key로 할수는 없으니(MongoDB에선 배열도 가능하긴 하지만) 
        # 수정이나 삭제시 첫번째 단어등을 사용하거나, _id나 별도 키가 필요할 수 있습니다.
        # Entity에서는 key_field="synonyms"로 잡았으나 부분배열 매칭 등 제약이 있을 수 있음.
        entity = SynonymDictionaryEntity(**req.model_dump())
        return await self.repo.create(entity)

    async def update(self, synonyms: list, req: SynonymDictionaryUpdateReq):
        update_data = req.model_dump(exclude_unset=True)
        if "status" not in update_data:
            update_data["status"] = DictionaryStatus.DRAFT
        return await self.repo.update(synonyms, update_data)

    async def delete(self, synonyms: list):
        return await self.repo.delete(synonyms)


class CorrectionDictionaryService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = CorrectionDictionaryRepository(db)

    async def get_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.search_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def get_admin_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.admin_search_deleted_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def create(self, req: CorrectionDictionaryCreateReq):
        entity = CorrectionDictionaryEntity(**req.model_dump())
        return await self.repo.create(entity)

    async def update(self, incorrect: str, req: CorrectionDictionaryUpdateReq):
        update_data = req.model_dump(exclude_unset=True)
        if "status" not in update_data:
            update_data["status"] = DictionaryStatus.DRAFT
        return await self.repo.update(incorrect, update_data)

    async def delete(self, incorrect: str):
        return await self.repo.delete(incorrect)


class StopwordDictionaryService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = StopwordDictionaryRepository(db)

    async def get_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.search_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def get_admin_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.admin_search_deleted_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def create(self, req: StopwordDictionaryCreateReq):
        entity = StopwordDictionaryEntity(**req.model_dump())
        return await self.repo.create(entity)

    async def update(self, word: str, req: StopwordDictionaryUpdateReq):
        update_data = req.model_dump(exclude_unset=True)
        if "status" not in update_data:
            update_data["status"] = DictionaryStatus.DRAFT
        return await self.repo.update(word, update_data)

    async def delete(self, word: str):
        return await self.repo.delete(word)
