import logging
from typing import Any, Optional

import aiohttp

from src.python.elasticsearch.config.settings.env_settings import settings

logger = logging.getLogger(__name__)


class PrometheusRepository:
    """Prometheus HTTP API와 통신하는 저수준 데이터 액세스 레이어."""

    def __init__(self, session: aiohttp.ClientSession, base_url: Optional[str] = None):
        self.session = session
        self.base_url = (base_url or settings.PROMETHEUS_URL).rstrip("/")

    async def query(self, promql: str) -> dict[str, Any]:
        """
        Prometheus instant query 실행.
        /api/v1/query
        """
        url = f"{self.base_url}/api/v1/query"
        params = {"query": promql}

        async with self.session.get(url, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.error(f"Prometheus query failed ({resp.status}): {text}")
                raise Exception(f"Prometheus query failed: {resp.status}")
            data = await resp.json()

        if data.get("status") != "success":
            raise Exception(f"Prometheus query error: {data.get('error', 'unknown')}")

        return data["data"]

    async def query_range(
        self,
        promql: str,
        start: str,
        end: str,
        step: str,
    ) -> dict[str, Any]:
        """
        Prometheus range query 실행.
        /api/v1/query_range
        """
        url = f"{self.base_url}/api/v1/query_range"
        params = {
            "query": promql,
            "start": start,
            "end": end,
            "step": step,
        }

        async with self.session.get(url, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.error(f"Prometheus range query failed ({resp.status}): {text}")
                raise Exception(f"Prometheus range query failed: {resp.status}")
            data = await resp.json()

        if data.get("status") != "success":
            raise Exception(f"Prometheus range query error: {data.get('error', 'unknown')}")

        return data["data"]
