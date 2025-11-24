import inspect
from elasticsearch import AsyncElasticsearch
from pydantic import ValidationError
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR
from typing import Literal

from src.python.elasticsearch.application.repository.elasticsearch.entities.cat_indices_entity import IndicesEntity, \
    IndexEntity
from src.python.elasticsearch.application.repository.elasticsearch.entities.cat_shard_entity import ShardEntity, \
    ShardsEntity
from src.python.elasticsearch.config.exceptions.biz_exceptions import BizException


class ElasticsearchCatRepository:
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

    async def get_shards_info(self, exclude_hidden: bool = True) -> ShardsEntity:
        try:
            hidden_filter_path = "*,-.*" if exclude_hidden else None
            h = "index,shard,prirep,state,node,store,docs,ur,ud,relocating_node,id"
            response = await self.es_client.cat.shards(index=hidden_filter_path, format="json", h=h)
            shards_info = []
            for shard in response:
                shards_info.append(ShardEntity(**shard))
            return ShardsEntity(shards=shards_info)
        except ValidationError as e:
            func_name = inspect.currentframe().f_code.co_name
            # 필요한 방식으로 처리
            raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"{func_name} entity parse error: {e}")
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"{func_name} entity unknown error: {e}")

    async def get_indices_info(self,
                               status_filter: Literal["all", "closed", "hidden", "none", "open"] = "all",
                               exclude_hidden: bool = True
                               ) -> IndicesEntity:
        try:
            hidden_filter_path = "*,-.*" if exclude_hidden else None
            response = await self.es_client.cat.indices(index=hidden_filter_path, expand_wildcards=status_filter, format="json")
            indices_info = []
            for index in response:
                indices_info.append(IndexEntity(**index))
            return IndicesEntity(indices=indices_info)
        except ValidationError as e:
            func_name = inspect.currentframe().f_code.co_name
            # 필요한 방식으로 처리
            raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"{func_name} entity parse error: {e}")
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"{func_name} entity unknown error: {e}")

    async def get_index_info(self, index_name: str) -> IndexEntity:
        try:
            response = await self.es_client.cat.indices(index=index_name, format="json")
            if not response:
                raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"Index {index_name} not found")
            return IndexEntity(**response[0])
        except ValidationError as e:
            func_name = inspect.currentframe().f_code.co_name
            # 필요한 방식으로 처리
            raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"{func_name} entity parse error: {e}")
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=f"{func_name} entity unknown error: {e}")