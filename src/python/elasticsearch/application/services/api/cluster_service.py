import json
import logging

from typing import Optional, List, Literal
from elasticsearch import AsyncElasticsearch

from src.python.elasticsearch.application.repository.elasticsearch.cluster_repository import \
    ElasticsearchClusterRepository
from src.python.elasticsearch.application.schemas.responses.cluster.cluster_health_res import ClusterHealthRes
from src.python.elasticsearch.application.services.mapper.cluster_health_mapper import ClusterHealthMapper
from src.python.elasticsearch.application.services.mapper.cluster_nodes_mapper import ClusterNodesMapper

logger = logging.getLogger(__name__)

class ElasticsearchClusterService:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def nodes(self):
        # 1. Respository 정의
        cluster_repository = ElasticsearchClusterRepository(self.es_client)

        # 2. ES 호출
        master_node_id = await cluster_repository.get_master_node()
        nodes_result = await cluster_repository.get_cluster_nodes()

        return ClusterNodesMapper.to_response(entity=nodes_result, master_node_id=master_node_id)

    async def health(self,
                     index: Optional[str | List[str]]
                     ) -> ClusterHealthRes:
        # 0. input valication
        index = index if index not in (None, [], "") else None

        # 1. Respository 정의
        cluster_repository = ElasticsearchClusterRepository(es_client=self.es_client)

        # 2. ES 호출
        result = await cluster_repository.get_cluster_health(index=index)

        return ClusterHealthMapper.to_response(result)