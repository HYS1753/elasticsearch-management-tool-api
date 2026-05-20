import pytest
from unittest.mock import AsyncMock, MagicMock
from src.python.elasticsearch.application.repository.mongodb.base_mongo_repository import BaseMongoRepository
from src.python.elasticsearch.application.repository.mongodb.entities.user_dictionary_entity import UserDictionaryEntity

@pytest.mark.unit
class TestBaseMongoRepositoryUnit:

    @pytest.fixture
    def mock_db(self):
        """Mock motor MongoDB database"""
        return MagicMock()

    @pytest.fixture
    def repository(self, mock_db):
        """Repository instance with mocked database"""
        return BaseMongoRepository(
            db=mock_db,
            collection_name="user_dictionary",
            model=UserDictionaryEntity,
            key_field="word"
        )

    @pytest.mark.asyncio
    async def test_create_new_entry(self, repository):
        repository.collection.find_one = AsyncMock(return_value=None)
        repository.collection.insert_one = AsyncMock()

        entity = UserDictionaryEntity(
            word="테스트단어",
            comment="테스트",
            author="admin",
            status="DRAFT"
        )
        result = await repository.create(entity)

        assert result.word == "테스트단어"
        assert result.index == 1
        repository.collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_entry(self, repository):
        repository.collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

        result = await repository.delete("테스트단어")

        assert result is True
        repository.collection.update_one.assert_called_once()
        
        called_args = repository.collection.update_one.call_args[0][1]
        assert called_args["$set"]["delete_yn"] == "Y"
        assert "updated_at" in called_args["$set"]
        assert "updated_at_kst" in called_args["$set"]
        assert "status" not in called_args["$set"]
        assert "approver" not in called_args["$set"]
