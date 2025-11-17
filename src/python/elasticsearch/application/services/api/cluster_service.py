import json
import logging

from typing import Optional, List, Literal
from elasticsearch import AsyncElasticsearch

from src.python.elasticsearch.application.repository.elasticsearch.cluster_repository import \
    ElasticsearchClusterRepository
from src.python.elasticsearch.application.schemas.responses.cluster.cluster_health_res import ClusterHealthRes
from src.python.elasticsearch.application.services.mapper.cluster_state_mapper import ClusterStateMapper
from src.python.elasticsearch.application.services.mapper.cluster_node_state_mapper import ClusterNodeStateMapper

logger = logging.getLogger(__name__)

class ElasticsearchClusterService:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def node_status(self):
        # 1. Respository 정의
        cluster_repository = ElasticsearchClusterRepository(self.es_client)

        # 2. ES 호출
        master_node_id = await cluster_repository.get_master_node()
        nodes_result = await cluster_repository.get_cluster_nodes()

        return ClusterNodeStateMapper.to_response(entity=nodes_result, master_node_id=master_node_id)

    async def cluster_state(self) -> ClusterHealthRes:
        # 1. Respository 정의
        cluster_repository = ElasticsearchClusterRepository(es_client=self.es_client)

        # 2. ES 호출
        result = await cluster_repository.get_cluster_health()

        return ClusterStateMapper.to_response(result)