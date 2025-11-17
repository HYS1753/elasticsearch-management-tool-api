import inspect
from elasticsearch import AsyncElasticsearch
from pydantic.v1 import ValidationError
from typing import Optional, List
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from src.python.elasticsearch.application.repository.elasticsearch.entities.cluster_health_entity import \
    ClusterHealthEntity
from src.python.elasticsearch.application.repository.elasticsearch.entities.nodes_entity import ClusterNodesEntity
from src.python.elasticsearch.config.exceptions.biz_exceptions import BizException


class ElasticsearchClusterRepository:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def get_master_node(self) -> str:
        try:
            response = await self.es_client.cat.master(format="json")
            master_node_id = response[0].get("id", "")
            return master_node_id
        except ValidationError as e:
            func_name = inspect.currentframe().f_code.co_name
            # 필요한 방식으로 처리
            raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"{func_name} entity parse error: {e}")
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"{func_name} entity unknown error: {e}")

    async def get_cluster_nodes(self) -> ClusterNodesEntity:
        """ 현재 클러스터 내 존재하는 노드 기본 정보 조회 (node Name, ID, IP, Roles...) """
        filter_path = "nodes.*.name,nodes.*.roles,nodes.*.ip,nodes.*.transport_address,nodes.*.settings.http.port"
        try:
            response = await self.es_client.nodes.info(filter_path=filter_path)
            return ClusterNodesEntity(**response)
        except ValidationError as e:
            func_name = inspect.currentframe().f_code.co_name
            # 필요한 방식으로 처리
            raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"{func_name} entity parse error: {e}")
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"{func_name} entity unknown error: {e}")

    async def get_cluster_health(self, index: Optional[str] = None) -> ClusterHealthEntity:
        response = await self.es_client.cluster.health(**{
            "index": index if index else None,
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
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"{func_name} entity unknown error: {e}")