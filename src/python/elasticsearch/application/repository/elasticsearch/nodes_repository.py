import inspect
from elasticsearch import AsyncElasticsearch
from pydantic.v1 import ValidationError
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from src.python.elasticsearch.application.repository.elasticsearch.entities.nodes_entity import NodesEntity
from src.python.elasticsearch.application.repository.elasticsearch.entities.nodes_stats_entity import NodesStatsEntity
from src.python.elasticsearch.config.exceptions.biz_exceptions import BizException


class ElasticsearchNodesRepository:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def get_nodes(self) -> NodesEntity:
        """ 현재 클러스터 내 존재하는 노드 기본 정보 조회 (node Name, ID, IP, Roles...) """
        filter_path = ("nodes.*.name,"
                       "nodes.*.roles,"
                       "nodes.*.ip,"
                       "nodes.*.transport_address,"
                       "nodes.*.settings.http.port")
        try:
            response = await self.es_client.nodes.info(filter_path=filter_path)
            return NodesEntity(**response)
        except ValidationError as e:
            func_name = inspect.currentframe().f_code.co_name
            # 필요한 방식으로 처리
            raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"{func_name} entity parse error: {e}")
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"{func_name} entity unknown error: {e}")

    async def get_nodes_stats(self, node_id: str) -> NodesStatsEntity:
        """ 지정한 노드의 상세 stat 정보 조회 """
        filter_path = ("nodes.*.indices.docs,"
                       "nodes.*.indices.search"
                       "nodes.*.os.cpu,"
                       "nodes.*.os.mem,"
                       "nodes.*.os.swap,"
                       "nodes.*.jvm.mem,"
                       "nodes.*.jvm.gc,"
                       "nodes.*.fs.total,"
                       "nodes.*.indexing_pressure,"
                       "nodes.*.thread_pool.search")
        try:
            response = await self.es_client.nodes.stats(filter_path=filter_path, node_id=node_id)
            return NodesStatsEntity(**response)
        except ValidationError as e:
            func_name = inspect.currentframe().f_code.co_name
            # 필요한 방식으로 처리
            raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"{func_name} entity parse error: {e}")
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"{func_name} entity unknown error: {e}")