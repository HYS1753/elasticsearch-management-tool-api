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

from src.python.elasticsearch.application.repository.mongodb.entities.dictionary_base_entity import get_now_utc, get_now_kst_str
from src.python.elasticsearch.config.exceptions.biz_exceptions import BizException
from fastapi import status


class UserDictionaryService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = UserDictionaryRepository(db)

    async def get_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.search_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def get_admin_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.admin_search_deleted_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def create(self, req: UserDictionaryCreateReq):
        # 1. key_field를 기준으로 데이터가 이미 존재하는지 조회 (delete_yn 필터 없이)
        existing_doc = await self.repo.collection.find_one({"word": req.word})
        
        if existing_doc:
            # delete_yn == "N" 이면 이미 존재하는 항목 에러
            if existing_doc.get("delete_yn") == "N":
                raise BizException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="이미 등록되어 있는 항목입니다."
                )
            # delete_yn == "Y" 이면 복구
            else:
                entity = UserDictionaryEntity(**req.model_dump())
                entity.index = existing_doc.get("index", 1)
                entity.delete_yn = "N"
                entity.status = DictionaryStatus.DRAFT
                entity.approver = None
                entity.applied_at = None
                entity.applied_at_kst = None
                entity.updated_at = get_now_utc()
                entity.updated_at_kst = get_now_kst_str()
                
                await self.repo.collection.replace_one(
                    {"_id": existing_doc["_id"]},
                    entity.model_dump()
                )
                return entity

        entity = UserDictionaryEntity(**req.model_dump())
        return await self.repo.create(entity)

    async def update(self, word: str, req: UserDictionaryUpdateReq):
        update_data = req.model_dump(exclude_unset=True)
        if "status" not in update_data:
            update_data["status"] = DictionaryStatus.DRAFT
        return await self.repo.update(word, update_data)

    async def delete(self, word: str):
        # Soft delete & Reset status/approval info
        update_data = {
            "delete_yn": "Y",
            "status": DictionaryStatus.DRAFT,
            "approver": None,
            "applied_at": None,
            "applied_at_kst": None,
            "updated_at": get_now_utc(),
            "updated_at_kst": get_now_kst_str()
        }
        result = await self.repo.collection.update_one(
            {"word": word},
            {"$set": update_data}
        )
        return result.modified_count > 0


class DecompoundDictionaryService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = DecompoundDictionaryRepository(db)

    async def get_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.search_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def get_admin_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.admin_search_deleted_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def create(self, req: DecompoundDictionaryCreateReq):
        existing_doc = await self.repo.collection.find_one({"compound_word": req.compound_word})
        
        if existing_doc:
            if existing_doc.get("delete_yn") == "N":
                raise BizException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="이미 등록되어 있는 항목입니다."
                )
            else:
                entity = DecompoundDictionaryEntity(**req.model_dump())
                entity.index = existing_doc.get("index", 1)
                entity.delete_yn = "N"
                entity.status = DictionaryStatus.DRAFT
                entity.approver = None
                entity.applied_at = None
                entity.applied_at_kst = None
                entity.updated_at = get_now_utc()
                entity.updated_at_kst = get_now_kst_str()
                
                await self.repo.collection.replace_one(
                    {"_id": existing_doc["_id"]},
                    entity.model_dump()
                )
                return entity

        entity = DecompoundDictionaryEntity(**req.model_dump())
        return await self.repo.create(entity)

    async def update(self, compound_word: str, req: DecompoundDictionaryUpdateReq):
        update_data = req.model_dump(exclude_unset=True)
        if "status" not in update_data:
            update_data["status"] = DictionaryStatus.DRAFT
        return await self.repo.update(compound_word, update_data)

    async def delete(self, compound_word: str):
        update_data = {
            "delete_yn": "Y",
            "status": DictionaryStatus.DRAFT,
            "approver": None,
            "applied_at": None,
            "applied_at_kst": None,
            "updated_at": get_now_utc(),
            "updated_at_kst": get_now_kst_str()
        }
        result = await self.repo.collection.update_one(
            {"compound_word": compound_word},
            {"$set": update_data}
        )
        return result.modified_count > 0


class SynonymDictionaryService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = SynonymDictionaryRepository(db)

    async def get_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.search_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def get_admin_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.admin_search_deleted_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def create(self, req: SynonymDictionaryCreateReq):
        existing_doc = await self.repo.collection.find_one({"synonyms": { "$all": req.synonyms }})
        
        if existing_doc:
            if existing_doc.get("delete_yn") == "N":
                raise BizException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="이미 등록되어 있는 항목입니다."
                )
            else:
                entity = SynonymDictionaryEntity(**req.model_dump())
                entity.index = existing_doc.get("index", 1)
                entity.delete_yn = "N"
                entity.status = DictionaryStatus.DRAFT
                entity.approver = None
                entity.applied_at = None
                entity.applied_at_kst = None
                entity.updated_at = get_now_utc()
                entity.updated_at_kst = get_now_kst_str()
                
                await self.repo.collection.replace_one(
                    {"_id": existing_doc["_id"]},
                    entity.model_dump()
                )
                return entity

        entity = SynonymDictionaryEntity(**req.model_dump())
        return await self.repo.create(entity)

    async def update(self, synonyms: list, req: SynonymDictionaryUpdateReq):
        update_data = req.model_dump(exclude_unset=True)
        if "status" not in update_data:
            update_data["status"] = DictionaryStatus.DRAFT
        return await self.repo.update(synonyms, update_data)

    async def delete(self, synonyms: list):
        update_data = {
            "delete_yn": "Y",
            "status": DictionaryStatus.DRAFT,
            "approver": None,
            "applied_at": None,
            "applied_at_kst": None,
            "updated_at": get_now_utc(),
            "updated_at_kst": get_now_kst_str()
        }
        result = await self.repo.collection.update_one(
            {"synonyms": synonyms},
            {"$set": update_data}
        )
        return result.modified_count > 0


class CorrectionDictionaryService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = CorrectionDictionaryRepository(db)

    async def get_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.search_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def get_admin_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.admin_search_deleted_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def create(self, req: CorrectionDictionaryCreateReq):
        existing_doc = await self.repo.collection.find_one({"incorrect": req.incorrect})
        
        if existing_doc:
            if existing_doc.get("delete_yn") == "N":
                raise BizException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="이미 등록되어 있는 항목입니다."
                )
            else:
                entity = CorrectionDictionaryEntity(**req.model_dump())
                entity.index = existing_doc.get("index", 1)
                entity.delete_yn = "N"
                entity.status = DictionaryStatus.DRAFT
                entity.approver = None
                entity.applied_at = None
                entity.applied_at_kst = None
                entity.updated_at = get_now_utc()
                entity.updated_at_kst = get_now_kst_str()
                
                await self.repo.collection.replace_one(
                    {"_id": existing_doc["_id"]},
                    entity.model_dump()
                )
                return entity

        entity = CorrectionDictionaryEntity(**req.model_dump())
        return await self.repo.create(entity)

    async def update(self, incorrect: str, req: CorrectionDictionaryUpdateReq):
        update_data = req.model_dump(exclude_unset=True)
        if "status" not in update_data:
            update_data["status"] = DictionaryStatus.DRAFT
        return await self.repo.update(incorrect, update_data)

    async def delete(self, incorrect: str):
        update_data = {
            "delete_yn": "Y",
            "status": DictionaryStatus.DRAFT,
            "approver": None,
            "applied_at": None,
            "applied_at_kst": None,
            "updated_at": get_now_utc(),
            "updated_at_kst": get_now_kst_str()
        }
        result = await self.repo.collection.update_one(
            {"incorrect": incorrect},
            {"$set": update_data}
        )
        return result.modified_count > 0


class StopwordDictionaryService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = StopwordDictionaryRepository(db)

    async def get_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.search_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def get_admin_list(self, keyword: str, skip: int, limit: int, sort_by: str, sort_order: int):
        return await self.repo.admin_search_deleted_by_keyword(keyword, skip, limit, sort_by, sort_order)

    async def create(self, req: StopwordDictionaryCreateReq):
        existing_doc = await self.repo.collection.find_one({"word": req.word})
        
        if existing_doc:
            if existing_doc.get("delete_yn") == "N":
                raise BizException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="이미 등록되어 있는 항목입니다."
                )
            else:
                entity = StopwordDictionaryEntity(**req.model_dump())
                entity.index = existing_doc.get("index", 1)
                entity.delete_yn = "N"
                entity.status = DictionaryStatus.DRAFT
                entity.approver = None
                entity.applied_at = None
                entity.applied_at_kst = None
                entity.updated_at = get_now_utc()
                entity.updated_at_kst = get_now_kst_str()
                
                await self.repo.collection.replace_one(
                    {"_id": existing_doc["_id"]},
                    entity.model_dump()
                )
                return entity

        entity = StopwordDictionaryEntity(**req.model_dump())
        return await self.repo.create(entity)

    async def update(self, word: str, req: StopwordDictionaryUpdateReq):
        update_data = req.model_dump(exclude_unset=True)
        if "status" not in update_data:
            update_data["status"] = DictionaryStatus.DRAFT
        return await self.repo.update(word, update_data)

    async def delete(self, word: str):
        update_data = {
            "delete_yn": "Y",
            "status": DictionaryStatus.DRAFT,
            "approver": None,
            "applied_at": None,
            "applied_at_kst": None,
            "updated_at": get_now_utc(),
            "updated_at_kst": get_now_kst_str()
        }
        result = await self.repo.collection.update_one(
            {"word": word},
            {"$set": update_data}
        )
        return result.modified_count > 0
