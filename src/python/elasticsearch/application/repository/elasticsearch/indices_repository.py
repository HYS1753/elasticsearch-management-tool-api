import inspect
import json
from typing import Any, Dict

from elasticsearch import AsyncElasticsearch, NotFoundError
from pydantic import ValidationError
from starlette.status import HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR

from src.python.elasticsearch.config.exceptions.biz_exceptions import BizException


class ElasticsearchIndicesRepository:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def get_index_settings(self, index_name: str) -> Dict[str, Any]:
        try:
            response = await self.es_client.indices.get_settings(
                index=index_name,
                flat_settings=True,
                include_defaults=False,
            )
            return response
        except NotFoundError:
            raise BizException(
                status_code=HTTP_404_NOT_FOUND,
                message=f"Index {index_name} not found",
            )
        except ValidationError as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"{func_name} entity parse error: {e}",
            )
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"{func_name} entity unknown error: {e}",
            )

    async def get_index_mappings(self, index_name: str) -> Dict[str, Any]:
        try:
            response = await self.es_client.indices.get_mapping(index=index_name)
            return response
        except NotFoundError:
            raise BizException(
                status_code=HTTP_404_NOT_FOUND,
                message=f"Index {index_name} not found",
            )
        except ValidationError as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"{func_name} entity parse error: {e}",
            )
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"{func_name} entity unknown error: {e}",
            )

    async def get_index_aliases(self, index_name: str) -> Dict[str, Any]:
        try:
            response = await self.es_client.indices.get_alias(index=index_name)
            return response
        except NotFoundError:
            raise BizException(
                status_code=HTTP_404_NOT_FOUND,
                message=f"Index {index_name} not found",
            )
        except ValidationError as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"{func_name} entity parse error: {e}",
            )
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"{func_name} entity unknown error: {e}",
            )

    async def get_index_stats(self, index_name: str) -> Dict[str, Any]:
        try:
            response = await self.es_client.indices.stats(
                index=index_name,
                metric=["docs", "store", "indexing", "search"],
            )
            return response
        except NotFoundError:
            raise BizException(
                status_code=HTTP_404_NOT_FOUND,
                message=f"Index {index_name} not found",
            )
        except ValidationError as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"{func_name} entity parse error: {e}",
            )
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"{func_name} entity unknown error: {e}",
            )

    @staticmethod
    def stringify_json(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, sort_keys=True)