import inspect
from elasticsearch import AsyncElasticsearch
from pydantic.v1 import ValidationError
from typing import Optional
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from src.python.elasticsearch.application.repository.elasticsearch.entities.cluster_health_entity import \
    ClusterHealthEntity
from src.python.elasticsearch.config.exceptions.biz_exceptions import BizException


class ElasticsearchClusterRepository:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def get_health(self, index: Optional[str]) -> ClusterHealthEntity:
        response = await self.es_client.cluster.health(**{
            "index": index,
            "level": "cluster",
            "local": False,
            "master_timeout": "30s",
            "timeout": "30s",
            "wait_for_status": None,
            "wait_for_no_relocating_shards": None,
            "wait_for_active_shards": None,
            "wait_for_nodes": None,
            "wait_for_events": None
        })

        try:
            return ClusterHealthEntity(**response)
        except ValidationError as e:
            func_name = inspect.currentframe().f_code.co_name
            # 필요한 방식으로 처리
            raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"{func_name} entity parse error: {e}")