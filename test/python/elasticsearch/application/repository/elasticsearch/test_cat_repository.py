"""
Tests for ElasticsearchCatRepository

단위 테스트: Mock ES client 사용
통합 테스트: 실제 ES 연결 사용
"""
import pytest
from src.python.elasticsearch.application.repository.elasticsearch.cat_repository import ElasticsearchCatRepository
from src.python.elasticsearch.application.repository.elasticsearch.entities.cat_indices_entity import IndicesEntity, IndexEntity
from src.python.elasticsearch.application.repository.elasticsearch.entities.cat_shard_entity import ShardsEntity
from test.python.elasticsearch.config.connections.test_es_client_factory import TestEsClientFactory


# ============================================
# Unit Tests
# ============================================

@pytest.mark.unit
class TestCatRepositoryUnit:
    """Unit tests with mock ES client"""

    async def test_get_master_node(self):
        """Test get_master_node"""
        mock_client = TestEsClientFactory.create_mock_client()
        mock_client.cat.master.return_value = [{"id": "node-123"}]
        repo = ElasticsearchCatRepository(mock_client)

        result = await repo.get_master_node()

        assert result == "node-123"

    async def test_get_shards_info(self):
        """Test get_shards_info"""
        mock_client = TestEsClientFactory.create_mock_client()
        mock_client.cat.shards.return_value = [
            {"index": "test", "shard": "0", "prirep": "p", "state": "STARTED"}
        ]
        repo = ElasticsearchCatRepository(mock_client)

        result = await repo.get_shards_info()

        assert isinstance(result, ShardsEntity)
        assert len(result.shards) == 1

    async def test_get_indices_info(self):
        """Test get_indices_info"""
        mock_client = TestEsClientFactory.create_mock_client()
        mock_client.cat.indices.return_value = [
            {"index": "test", "uuid": "123", "health": "green", "status": "open"}
        ]
        repo = ElasticsearchCatRepository(mock_client)

        result = await repo.get_indices_info()

        assert isinstance(result, IndicesEntity)
        assert len(result.indices) == 1

    async def test_get_index_info(self):
        """Test get_index_info"""
        mock_client = TestEsClientFactory.create_mock_client()
        mock_client.cat.indices.return_value = [
            {"index": "test", "uuid": "123", "health": "green", "status": "open"}
        ]
        repo = ElasticsearchCatRepository(mock_client)

        result = await repo.get_index_info("test")

        assert isinstance(result, IndexEntity)
        assert result.index == "test"



# ============================================
# Integration Tests
# ============================================

@pytest.mark.integration
class TestCatRepositoryIntegration:
    """Integration tests with real ES client"""

    async def test_get_master_node(self):
        """Test get_master_node with real ES"""
        real_client = TestEsClientFactory.create_real_client()

        try:
            if not await real_client.ping():
                pytest.skip("ES not available")

            repo = ElasticsearchCatRepository(real_client)
            result = await repo.get_master_node()

            assert isinstance(result, str)
            assert len(result) > 0
        finally:
            await real_client.close()

    async def test_get_shards_info(self):
        """Test get_shards_info with real ES"""
        real_client = TestEsClientFactory.create_real_client()

        try:
            if not await real_client.ping():
                pytest.skip("ES not available")

            repo = ElasticsearchCatRepository(real_client)
            result = await repo.get_shards_info()

            assert isinstance(result, ShardsEntity)
            assert isinstance(result.shards, list)
        finally:
            await real_client.close()

    async def test_get_indices_info(self):
        """Test get_indices_info with real ES"""
        real_client = TestEsClientFactory.create_real_client()

        try:
            if not await real_client.ping():
                pytest.skip("ES not available")

            repo = ElasticsearchCatRepository(real_client)
            result = await repo.get_indices_info()

            assert isinstance(result, IndicesEntity)
            assert isinstance(result.indices, list)
        finally:
            await real_client.close()

    async def test_get_index_info(self):
        """Test get_index_info with real ES"""
        real_client = TestEsClientFactory.create_real_client()

        try:
            if not await real_client.ping():
                pytest.skip("ES not available")

            test_index_name = "test"
            repo = ElasticsearchCatRepository(real_client)
            result: IndexEntity = await repo.get_index_info(index_name=test_index_name)

            assert isinstance(result, IndexEntity)
            assert result.index == test_index_name
        finally:
            await real_client.close()


