"""
Test ES Connection Helper

테스트용 ES 클라이언트 생성 헬퍼
- 단위 테스트용: Mock client
- 통합 테스트용: Real client
"""
from unittest.mock import AsyncMock, MagicMock
from elasticsearch import AsyncElasticsearch
from src.python.elasticsearch.config.settings.env_settings import Settings


class TestEsClientFactory:
    """테스트용 ES 클라이언트 팩토리"""

    @staticmethod
    def create_mock_client() -> AsyncMock:
        """
        단위 테스트용 Mock ES client 생성

        Returns:
            AsyncMock: Mock된 AsyncElasticsearch 클라이언트
        """
        mock = AsyncMock(spec=AsyncElasticsearch)

        # Cat API
        mock.cat = MagicMock()
        mock.cat.master = AsyncMock()
        mock.cat.shards = AsyncMock()
        mock.cat.indices = AsyncMock()

        # Cluster API
        mock.cluster = MagicMock()
        mock.cluster.health = AsyncMock()
        mock.cluster.stats = AsyncMock()

        # Indices API
        mock.indices = MagicMock()
        mock.indices.get = AsyncMock()
        mock.indices.stats = AsyncMock()

        # Nodes API
        mock.nodes = MagicMock()
        mock.nodes.info = AsyncMock()
        mock.nodes.stats = AsyncMock()

        # Common
        mock.ping = AsyncMock(return_value=True)
        mock.transport = MagicMock()
        mock.transport.close = AsyncMock()

        return mock

    @staticmethod
    def create_real_client(settings: Settings = None) -> AsyncElasticsearch:
        """
        통합 테스트용 실제 ES client 생성

        Args:
            settings: Settings 객체 (None이면 자동 생성)

        Returns:
            AsyncElasticsearch: 실제 ES 클라이언트
        """
        if settings is None:
            settings = Settings()

        return AsyncElasticsearch(
            hosts=settings.GET_ES_HOST,
            basic_auth=(settings.ES_USER_ID, settings.ES_USER_PW) if settings.ES_USER_ID else None,
            api_key=settings.ES_API_KEY if settings.ES_API_KEY else None,
            verify_certs=settings.ES_VERIFY_CERTS,
            ssl_show_warn=False,
        )

