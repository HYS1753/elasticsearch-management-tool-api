import pytest
from unittest.mock import AsyncMock, MagicMock
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.python.elasticsearch.application.services.api.dictionary_service import UserDictionaryService
from src.python.elasticsearch.application.schemas.requests.dictionary.dictionary_req import UserDictionaryCreateReq
from src.python.elasticsearch.application.repository.mongodb.entities.user_dictionary_entity import UserDictionaryEntity
from src.python.elasticsearch.config.exceptions.biz_exceptions import BizException
from src.python.elasticsearch.common.enums.dictionary_status import DictionaryStatus

@pytest.mark.unit
class TestUserDictionaryServiceUnit:

    @pytest.fixture
    def mock_db(self):
        return MagicMock(spec=AsyncIOMotorDatabase)

    @pytest.fixture
    def service(self, mock_db):
        return UserDictionaryService(mock_db)

    @pytest.mark.asyncio
    async def test_create_new_entry(self, service):
        # 1. 존재하지 않는 경우: find_one -> None
        service.repo.collection.find_one = AsyncMock(return_value=None)
        service.repo.create = AsyncMock(return_value=MagicMock())

        req = UserDictionaryCreateReq(
            word="테스트단어",
            comment="테스트설명",
            author="admin"
        )
        
        await service.create(req)

        service.repo.collection.find_one.assert_called_once_with({"word": "테스트단어"})
        service.repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_duplicate_active_entry_raises_exception(self, service):
        # 2. 존재하는 경우 (delete_yn == "N") -> 에러 발생
        existing_doc = {
            "_id": "some_id",
            "word": "테스트단어",
            "delete_yn": "N",
            "index": 1,
            "status": "APPROVED"
        }
        service.repo.collection.find_one = AsyncMock(return_value=existing_doc)

        req = UserDictionaryCreateReq(
            word="테스트단어",
            comment="테스트설명",
            author="admin"
        )

        with pytest.raises(BizException) as excinfo:
            await service.create(req)

        assert excinfo.value.status_code == 400
        assert "이미 등록되어 있는 항목입니다." in excinfo.value.detail

    @pytest.mark.asyncio
    async def test_create_duplicate_deleted_entry_restores(self, service):
        # 3. 존재하는 경우 (delete_yn == "Y") -> 복구 처리
        existing_doc = {
            "_id": "some_id",
            "word": "테스트단어",
            "delete_yn": "Y",
            "index": 55,
            "status": "APPROVED",
            "approver": "some_admin"
        }
        service.repo.collection.find_one = AsyncMock(return_value=existing_doc)
        service.repo.collection.replace_one = AsyncMock()

        req = UserDictionaryCreateReq(
            word="테스트단어",
            comment="새로운설명",
            author="new_admin"
        )

        result = await service.create(req)

        assert result.word == "테스트단어"
        assert result.index == 55
        assert result.delete_yn == "N"
        assert result.status == DictionaryStatus.DRAFT
        assert result.approver is None
        assert result.applied_at is None
        
        service.repo.collection.replace_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_entry(self, service):
        # 4. 삭제 시 status, approval 초기화 쿼리 검증
        service.repo.collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

        result = await service.delete("테스트단어")

        assert result is True
        service.repo.collection.update_one.assert_called_once()
        
        called_args = service.repo.collection.update_one.call_args[0][1]
        assert called_args["$set"]["delete_yn"] == "Y"
        assert called_args["$set"]["status"] == DictionaryStatus.DRAFT
        assert called_args["$set"]["approver"] is None
        assert called_args["$set"]["applied_at"] is None
        assert called_args["$set"]["applied_at_kst"] is None
