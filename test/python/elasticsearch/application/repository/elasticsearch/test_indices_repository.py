"""
Tests for ElasticsearchIndicesRepository

단위 테스트: Mock ES client 사용
통합 테스트: 실제 ES 연결 사용
"""
import pytest
from elastic_transport import ObjectApiResponse
from src.python.elasticsearch.application.repository.elasticsearch.entities.cat_indices_entity import IndicesEntity, IndexEntity
from src.python.elasticsearch.application.repository.elasticsearch.indices_repository import \
    ElasticsearchIndicesRepository
from test.python.elasticsearch.config.connections.test_es_client_factory import TestEsClientFactory


# ============================================
# Unit Tests
# ============================================

@pytest.mark.unit
class TestIndicesRepositoryUnit:
    """Unit tests with mock ES client"""

    async def test_get_index_settings(self):
        """Test get_index_settings"""
        mock_client = TestEsClientFactory.create_mock_client()
        mock_client.indices.get_settings.return_value = {
            "test": {"settings": {}}
        }
        repo = ElasticsearchIndicesRepository(mock_client)

        test_index_name = "test"
        result = await repo.get_index_settings(index_name=test_index_name)

        assert isinstance(result, dict)
        assert "settings" in result[test_index_name]

    async def test_get_index_mapping(self):
        """Test get_index_mappings"""
        mock_client = TestEsClientFactory.create_mock_client()
        mock_client.indices.get_mapping.return_value = {
            "test": {"mappings": {}}
        }
        repo = ElasticsearchIndicesRepository(mock_client)

        test_index_name = "test"
        result = await repo.get_index_mappings(index_name=test_index_name)

        assert isinstance(result, dict)
        assert "mappings" in result[test_index_name]


# ============================================
# Integration Tests
# ============================================

@pytest.mark.integration
class TestCatRepositoryIntegration:
    """Integration tests with real ES client"""

    async def test_get_index_settings(self):
        """Test get_index_settings with real ES"""
        real_client = TestEsClientFactory.create_real_client()

        try:
            if not await real_client.ping():
                pytest.skip("ES not available")

            test_index_name = "test"
            repo = ElasticsearchIndicesRepository(real_client)
            result = await repo.get_index_settings(index_name=test_index_name)

            assert isinstance(result, (dict, ObjectApiResponse))
            assert "settings" in result[test_index_name]
        finally:
            await real_client.close()

    async def test_get_index_mapping(self):
        """Test get_index_mappings with real ES"""
        real_client = TestEsClientFactory.create_real_client()

        try:
            if not await real_client.ping():
                pytest.skip("ES not available")

            test_index_name = "test"
            repo = ElasticsearchIndicesRepository(real_client)
            result = await repo.get_index_mappings(index_name=test_index_name)

            assert isinstance(result, (dict, ObjectApiResponse))
            assert "mappings" in result[test_index_name]
        finally:
            await real_client.close()


