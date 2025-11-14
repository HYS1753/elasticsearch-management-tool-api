import json
import logging

from typing import Optional, List, Literal
from elasticsearch import AsyncElasticsearch

from src.python.elasticsearch.application.repository.elasticsearch.cluster_repository import \
    ElasticsearchClusterRepository
from src.python.elasticsearch.application.schemas.responses.cluster.cluster_health_res import ClusterHealthRes

logger = logging.getLogger(__name__)

class ElasticsearchClusterService:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def health(self,
                     index: Optional[str | List[str]],
                     level: Literal["cluster", "indices", "shards"] | None
                     ) -> ClusterHealthRes:
        # 0. input valication
        index = index if index not in (None, [], "") else None
        level = level if level in ("cluster", "indices", "shards") else None

        # 1. Respository 정의
        cluster_repository = ElasticsearchClusterRepository(es_client=self.es_client)

        # 2. input params 정의
        input_params = {
            "index": index,
            "level": level,
            "local": False,
            "master_timeout": "30s",
            "timeout": "30s",
            "wait_for_status": None,
            "wait_for_no_relocating_shards": None,
            "wait_for_active_shards": None,
            "wait_for_nodes": None,
            "wait_for_events": None
        }

        # 3. ES 호출
        result = await cluster_repository.get_health(params=input_params)

        return ClusterHealthRes.model_validate(result.copy())