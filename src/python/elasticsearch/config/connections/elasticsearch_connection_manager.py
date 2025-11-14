
from elasticsearch import AsyncElasticsearch
from fastapi import FastAPI
from pathlib import Path
from src.python.elasticsearch.config.settings.env_settings import settings

class EsConnectionManager:
    def __init__(self):
        hosts = settings.GET_ES_HOST
        api_key = settings.ES_API_KEY
        user_id = settings.ES_USER_ID
        user_pw = settings.ES_USER_PW
        verify_certs = settings.ES_VERIFY_CERTS
        ca_certs = settings.ES_CERTS
        max_connections = settings.ES_MAX_CONNECTION
        timeout = settings.ES_TIMEOUT

        # Thread pool
        # 기본 인자 딕셔너리 설정
        es_kwargs = {
            "hosts": hosts,
            "ssl_show_warn": False,
            "connections_per_node": max_connections,
            "request_timeout": timeout
        }

        # api_key 값이 None 이거나 빈 문자열이 아니라면 추가
        if api_key not in (None, ""):
            es_kwargs["api_key"] = str(api_key)

        if user_id not in (None, "") and user_pw not in (None, ""):
            es_kwargs["user_id"] = str(user_id)
            es_kwargs["user_pw"] = str(user_pw)

        # verify_certs 값이 None 이거나 빈 문자열이 아니라면 추가
        if verify_certs:
            es_kwargs["verify_certs"] = verify_certs
        else:
            es_kwargs["verify_certs"] = False

        # ca_certs 값이 None 이거나 빈 문자열이 아니라면 추가
        if ca_certs not in (None, ""):
            BASE_DIR = Path(__file__).resolve().parents[5]  # ROOT_DIR
            es_kwargs["ca_certs"] = (BASE_DIR / ca_certs).resolve()

        self.client = AsyncElasticsearch(**es_kwargs)

    def get_client(self):
        return self.client

    async def is_connected(self) -> bool:
        """연결 상태 확인"""
        if not self.client:
            return False

        try:
            return await self.client.ping()
        except Exception:
            return False

    async def close(self):
        await self.client.transport.close()

# FastAPI의 전역 객체에 Elasticsearch 관리 객체를 저장
def init_elasticsearch_connection(app: FastAPI):
    app.state.es_connection_manager = EsConnectionManager()

def get_elasticsearch_client(app: FastAPI) -> AsyncElasticsearch:
    return app.state.es_connection_manager.get_client()

async def close_elasticsearch_connection(app: FastAPI):
    await app.state.es_connection_manager.close()

async def is_elasticsearch_connected(app: FastAPI) -> bool:
    """Elasticsearch 연결 상태 확인"""
    return await app.state.es_connection_manager.is_connected()
