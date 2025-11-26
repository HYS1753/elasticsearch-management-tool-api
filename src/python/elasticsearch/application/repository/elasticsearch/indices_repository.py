import inspect
from elasticsearch import AsyncElasticsearch
from pydantic import ValidationError
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from src.python.elasticsearch.application.repository.elasticsearch.entities.cat_shard_entity import ShardEntity, \
    ShardsEntity
from src.python.elasticsearch.config.exceptions.biz_exceptions import BizException


class ElasticsearchIndicesRepository:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def get_index_settings(self, index_name: str) -> str:
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

    async def get_index_mappings(self, index_name: str) -> ShardsEntity:
        pass