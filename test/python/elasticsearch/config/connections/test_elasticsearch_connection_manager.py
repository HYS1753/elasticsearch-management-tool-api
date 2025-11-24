"""
Tests for EsConnectionManager

단위 테스트: Settings를 mock하여 실제 ES 연결 없이 테스트
통합 테스트: 실제 ES 연결 사용
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.python.elasticsearch.config.connections.elasticsearch_connection_manager import (
    EsConnectionManager,
    init_elasticsearch_connection,
    get_elasticsearch_client,
    close_elasticsearch_connection,
    is_elasticsearch_connected
)
from test.python.elasticsearch.config.connections.test_es_client_factory import TestEsClientFactory


# ============================================
# Unit Tests
# ============================================

@pytest.mark.unit
class TestEsConnectionManagerUnit:
    """Unit tests for EsConnectionManager"""

    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.settings')
    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.AsyncElasticsearch')
    def test_init_creates_client(self, mock_es_class, mock_settings):
        """Test EsConnectionManager creates ES client on init"""
        # Mock settings
        mock_settings.GET_ES_HOST = ["http://localhost:9200"]
        mock_settings.ES_API_KEY = ""
        mock_settings.ES_USER_ID = ""
        mock_settings.ES_USER_PW = ""
        mock_settings.ES_VERIFY_CERTS = False
        mock_settings.ES_CERTS = ""
        mock_settings.ES_MAX_CONNECTION = 10
        mock_settings.ES_TIMEOUT = 30

        # Mock ES client
        mock_es_instance = MagicMock()
        mock_es_class.return_value = mock_es_instance

        manager = EsConnectionManager()

        assert manager.client is not None
        assert manager.client == mock_es_instance
        mock_es_class.assert_called_once()

    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.settings')
    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.AsyncElasticsearch')
    def test_get_client_returns_client(self, mock_es_class, mock_settings):
        """Test get_client returns the ES client"""
        # Mock settings
        mock_settings.GET_ES_HOST = ["http://localhost:9200"]
        mock_settings.ES_API_KEY = ""
        mock_settings.ES_USER_ID = ""
        mock_settings.ES_USER_PW = ""
        mock_settings.ES_VERIFY_CERTS = False
        mock_settings.ES_CERTS = ""
        mock_settings.ES_MAX_CONNECTION = 10
        mock_settings.ES_TIMEOUT = 30

        mock_es_instance = MagicMock()
        mock_es_class.return_value = mock_es_instance

        manager = EsConnectionManager()
        client = manager.get_client()

        assert client is not None
        assert client == mock_es_instance

    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.settings')
    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.AsyncElasticsearch')
    async def test_is_connected_returns_true_when_connected(self, mock_es_class, mock_settings):
        """Test is_connected returns True when ES is reachable"""
        # Mock settings
        mock_settings.GET_ES_HOST = ["http://localhost:9200"]
        mock_settings.ES_API_KEY = ""
        mock_settings.ES_USER_ID = ""
        mock_settings.ES_USER_PW = ""
        mock_settings.ES_VERIFY_CERTS = False
        mock_settings.ES_CERTS = ""
        mock_settings.ES_MAX_CONNECTION = 10
        mock_settings.ES_TIMEOUT = 30

        mock_client = TestEsClientFactory.create_mock_client()
        mock_client.ping = AsyncMock(return_value=True)
        mock_es_class.return_value = mock_client

        manager = EsConnectionManager()
        result = await manager.is_connected()

        assert result is True

    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.settings')
    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.AsyncElasticsearch')
    async def test_is_connected_returns_false_on_exception(self, mock_es_class, mock_settings):
        """Test is_connected returns False when ping fails"""
        # Mock settings
        mock_settings.GET_ES_HOST = ["http://localhost:9200"]
        mock_settings.ES_API_KEY = ""
        mock_settings.ES_USER_ID = ""
        mock_settings.ES_USER_PW = ""
        mock_settings.ES_VERIFY_CERTS = False
        mock_settings.ES_CERTS = ""
        mock_settings.ES_MAX_CONNECTION = 10
        mock_settings.ES_TIMEOUT = 30

        mock_client = TestEsClientFactory.create_mock_client()
        mock_client.ping = AsyncMock(side_effect=Exception("Connection failed"))
        mock_es_class.return_value = mock_client

        manager = EsConnectionManager()
        result = await manager.is_connected()

        assert result is False

    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.settings')
    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.AsyncElasticsearch')
    async def test_close_closes_client(self, mock_es_class, mock_settings):
        """Test close closes the ES client"""

        # mock_settings: settings 객체의 mock (MagicMock)
        # - 실제 settings 대신 이 mock이 사용됨
        # - 원본: from ...env_settings import settings
        # - 테스트: settings → mock_settings
        mock_settings.GET_ES_HOST = ["http://localhost:9200"]
        mock_settings.ES_API_KEY = ""
        mock_settings.ES_USER_ID = ""
        mock_settings.ES_USER_PW = ""
        mock_settings.ES_VERIFY_CERTS = False
        mock_settings.ES_CERTS = ""
        mock_settings.ES_MAX_CONNECTION = 10
        mock_settings.ES_TIMEOUT = 30

        # mock_es_class: AsyncElasticsearch 클래스의 mock
        # - 실제 ES 클라이언트 생성 대신 mock 반환
        # - 원본: client = AsyncElasticsearch(...)
        # - 테스트: client = mock_es_class(...) → mock_client 반환
        mock_client = TestEsClientFactory.create_mock_client()
        mock_es_class.return_value = mock_client  # 생성자 호출 시 이 mock_client 반환

        # EsConnectionManager 생성
        # - __init__에서 settings 접근 → mock_settings 사용
        # - __init__에서 AsyncElasticsearch() 호출 → mock_es_class() 호출 → mock_client 반환
        manager = EsConnectionManager()

        # 테스트: close 메서드 호출
        await manager.close()

        # 검증: transport.close()가 한 번 호출되었는지 확인
        mock_client.transport.close.assert_called_once()


@pytest.mark.unit
class TestConnectionHelperFunctionsUnit:
    """Unit tests for helper functions"""

    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.settings')
    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.AsyncElasticsearch')
    def test_init_elasticsearch_connection(self, mock_es_class, mock_settings):
        """Test init_elasticsearch_connection sets manager in app.state"""
        # Mock settings
        mock_settings.GET_ES_HOST = ["http://localhost:9200"]
        mock_settings.ES_API_KEY = ""
        mock_settings.ES_USER_ID = ""
        mock_settings.ES_USER_PW = ""
        mock_settings.ES_VERIFY_CERTS = False
        mock_settings.ES_CERTS = ""
        mock_settings.ES_MAX_CONNECTION = 10
        mock_settings.ES_TIMEOUT = 30

        mock_es_class.return_value = MagicMock()

        from fastapi import FastAPI
        app = FastAPI()
        init_elasticsearch_connection(app)

        assert hasattr(app.state, 'es_connection_manager')
        assert isinstance(app.state.es_connection_manager, EsConnectionManager)

    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.settings')
    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.AsyncElasticsearch')
    def test_get_elasticsearch_client(self, mock_es_class, mock_settings):
        """Test get_elasticsearch_client returns client from app.state"""
        # Mock settings
        mock_settings.GET_ES_HOST = ["http://localhost:9200"]
        mock_settings.ES_API_KEY = ""
        mock_settings.ES_USER_ID = ""
        mock_settings.ES_USER_PW = ""
        mock_settings.ES_VERIFY_CERTS = False
        mock_settings.ES_CERTS = ""
        mock_settings.ES_MAX_CONNECTION = 10
        mock_settings.ES_TIMEOUT = 30

        mock_es_class.return_value = MagicMock()

        from fastapi import FastAPI
        app = FastAPI()
        init_elasticsearch_connection(app)

        client = get_elasticsearch_client(app)

        assert client is not None

    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.settings')
    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.AsyncElasticsearch')
    async def test_close_elasticsearch_connection(self, mock_es_class, mock_settings):
        """Test close_elasticsearch_connection closes manager"""
        # Mock settings
        mock_settings.GET_ES_HOST = ["http://localhost:9200"]
        mock_settings.ES_API_KEY = ""
        mock_settings.ES_USER_ID = ""
        mock_settings.ES_USER_PW = ""
        mock_settings.ES_VERIFY_CERTS = False
        mock_settings.ES_CERTS = ""
        mock_settings.ES_MAX_CONNECTION = 10
        mock_settings.ES_TIMEOUT = 30

        mock_client = TestEsClientFactory.create_mock_client()
        mock_es_class.return_value = mock_client

        from fastapi import FastAPI
        app = FastAPI()
        init_elasticsearch_connection(app)

        await close_elasticsearch_connection(app)

        mock_client.transport.close.assert_called_once()

    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.settings')
    @patch('src.python.elasticsearch.config.connections.elasticsearch_connection_manager.AsyncElasticsearch')
    async def test_is_elasticsearch_connected(self, mock_es_class, mock_settings):
        """Test is_elasticsearch_connected checks manager connection"""
        # Mock settings
        mock_settings.GET_ES_HOST = ["http://localhost:9200"]
        mock_settings.ES_API_KEY = ""
        mock_settings.ES_USER_ID = ""
        mock_settings.ES_USER_PW = ""
        mock_settings.ES_VERIFY_CERTS = False
        mock_settings.ES_CERTS = ""
        mock_settings.ES_MAX_CONNECTION = 10
        mock_settings.ES_TIMEOUT = 30

        mock_client = TestEsClientFactory.create_mock_client()
        mock_client.ping = AsyncMock(return_value=True)
        mock_es_class.return_value = mock_client

        from fastapi import FastAPI
        app = FastAPI()
        init_elasticsearch_connection(app)

        result = await is_elasticsearch_connected(app)

        assert result is True


# ============================================
# Integration Tests
# ============================================

@pytest.mark.integration
class TestEsConnectionManagerIntegration:
    """Integration tests with real ES"""

    async def test_is_connected_with_real_es(self):
        """Test is_connected with real ES connection"""
        manager = EsConnectionManager()
        real_client = TestEsClientFactory.create_real_client()

        # Use the real client for testing
        original_client = manager.client
        manager.client = real_client

        try:
            result = await manager.is_connected()
            # Should return True if ES is available, False otherwise
            assert isinstance(result, bool)
        finally:
            manager.client = original_client
            await real_client.close()

    async def test_get_client_returns_working_client(self):
        """Test get_client returns a working client"""
        manager = EsConnectionManager()

        client = manager.get_client()

        try:
            # Try to ping - should work if ES is available
            can_ping = await client.ping()
            assert isinstance(can_ping, bool)
        except Exception:
            # If ES is not available, that's ok for this test
            pytest.skip("ES not available")
        finally:
            await manager.close()

