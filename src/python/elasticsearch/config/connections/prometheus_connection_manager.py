import aiohttp
import logging
from fastapi import FastAPI
from src.python.elasticsearch.config.settings.env_settings import settings

logger = logging.getLogger(__name__)

class PrometheusConnectionManager:
    """Prometheus aiohttp.ClientSession 싱글톤 커넥션 매니저."""
    def __init__(self):
        self.base_url = settings.PROMETHEUS_URL.rstrip("/")
        self.session: aiohttp.ClientSession | None = None

    async def init_session(self):
        """HTTP 클라이언트 세션 초기화"""
        if not self.session or self.session.closed:
            # 적절한 커넥션 풀 크기 및 타임아웃 구성
            connector = aiohttp.TCPConnector(limit=100, keepalive_timeout=30)
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout
            )
            logger.info("Initialized Prometheus aiohttp ClientSession singleton pool.")

    def get_session(self) -> aiohttp.ClientSession:
        """세션 객체 반환"""
        if not self.session or self.session.closed:
            raise RuntimeError("Prometheus ClientSession is not initialized.")
        return self.session

    async def close(self):
        """세션 종료"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("Closed Prometheus aiohttp ClientSession singleton pool.")
            self.session = None


def init_prometheus_connection(app: FastAPI):
    """FastAPI state에 커넥션 매니저 인스턴스 생성"""
    app.state.prometheus_connection_manager = PrometheusConnectionManager()

async def start_prometheus_connection(app: FastAPI):
    """애플리케이션 시작 시 세션 생성"""
    await app.state.prometheus_connection_manager.init_session()

def get_prometheus_session(app: FastAPI) -> aiohttp.ClientSession:
    """애플리케이션 state에서 세션 조회"""
    return app.state.prometheus_connection_manager.get_session()

async def close_prometheus_connection(app: FastAPI):
    """애플리케이션 종료 시 세션 닫기"""
    if hasattr(app.state, "prometheus_connection_manager"):
        await app.state.prometheus_connection_manager.close()
