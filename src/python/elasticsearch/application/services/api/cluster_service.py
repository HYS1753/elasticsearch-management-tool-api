import json
import logging

from typing import Optional, List, Literal
from elasticsearch import AsyncElasticsearch

from src.python.elasticsearch.application.repository.elasticsearch.cat_repository import ElasticsearchCatRepository
from src.python.elasticsearch.application.repository.elasticsearch.cluster_repository import \
    ElasticsearchClusterRepository
from src.python.elasticsearch.application.repository.elasticsearch.nodes_repository import ElasticsearchNodesRepository
from src.python.elasticsearch.application.schemas.responses.cluster.cluster_status_res import ClusterStatusRes
from src.python.elasticsearch.application.schemas.responses.cluster.node_status_res import NodesStatusRes
from src.python.elasticsearch.application.services.mapper.cluster_status_mapper import ClusterStatusMapper
from src.python.elasticsearch.application.services.mapper.node_status_mapper import NodeStatusMapper

logger = logging.getLogger(__name__)

class ClusterService:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def node_status(self) -> NodesStatusRes:
        # 1. Respository 정의
        cat_repository = ElasticsearchCatRepository(self.es_client)
        nodes_repository = ElasticsearchNodesRepository(self.es_client)

        # 2. ES 호출
        master_node_id = await cat_repository.get_master_node()
        nodes_result = await nodes_repository.get_nodes()
        nodes_stats_result = {}
        for key, _ in nodes_result.nodes.items():
            nodes_stats_result[key] = await nodes_repository.get_nodes_stats(key)

        return NodeStatusMapper.to_response(master_node_id=master_node_id, nodes_entity=nodes_result, nodes_stats=nodes_stats_result)

    async def cluster_status(self) -> ClusterStatusRes:
        # 1. Respository 정의
        cluster_repository = ElasticsearchClusterRepository(es_client=self.es_client)

        # 2. ES 호출
        result = await cluster_repository.get_cluster_health()

        return ClusterStatusMapper.to_response(result)