import inspect
import json
from typing import Any, Dict

from elasticsearch import AsyncElasticsearch, NotFoundError, BadRequestError
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
        except BadRequestError as e:
            error_type = ""
            try:
                error_type = e.body.get("error", {}).get("type", "")
            except Exception:
                error_type = ""

            if error_type == "index_closed_exception":
                return {
                    "_shards": {
                        "total": 0,
                        "successful": 0,
                        "failed": 0,
                    },
                    "_all": {
                        "primaries": {
                            "docs": {
                                "count": 0,
                                "deleted": 0,
                            },
                            "store": {
                                "size_in_bytes": 0,
                            },
                        },
                        "total": {
                            "docs": {
                                "count": 0,
                                "deleted": 0,
                            },
                            "store": {
                                "size_in_bytes": 0,
                            },
                        },
                    },
                    "indices": {},
                }

            func_name = inspect.currentframe().f_code.co_name
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"{func_name} entity unknown error: {e}",
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

    async def open_index(self, index_name: str) -> Dict[str, Any]:
        try:
            return await self.es_client.indices.open(index=index_name)
        except NotFoundError:
            raise BizException(
                status_code=HTTP_404_NOT_FOUND,
                message=f"Index {index_name} not found",
            )
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"{func_name} error: {e}",
            )

    async def close_index(self, index_name: str) -> Dict[str, Any]:
        try:
            return await self.es_client.indices.close(index=index_name)
        except NotFoundError:
            raise BizException(
                status_code=HTTP_404_NOT_FOUND,
                message=f"Index {index_name} not found",
            )
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"{func_name} error: {e}",
            )

    async def update_read_only(self, index_name: str, read_only: bool) -> Dict[str, Any]:
        try:
            return await self.es_client.indices.put_settings(
                index=index_name,
                settings={
                    "index.blocks.read_only": read_only,
                },
            )
        except NotFoundError:
            raise BizException(
                status_code=HTTP_404_NOT_FOUND,
                message=f"Index {index_name} not found",
            )
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"{func_name} error: {e}",
            )

    async def refresh_index(self, index_name: str) -> Dict[str, Any]:
        try:
            return await self.es_client.indices.refresh(index=index_name)
        except NotFoundError:
            raise BizException(
                status_code=HTTP_404_NOT_FOUND,
                message=f"Index {index_name} not found",
            )
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"{func_name} error: {e}",
            )

    async def flush_index(self, index_name: str) -> Dict[str, Any]:
        try:
            return await self.es_client.indices.flush(index=index_name)
        except NotFoundError:
            raise BizException(
                status_code=HTTP_404_NOT_FOUND,
                message=f"Index {index_name} not found",
            )
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"{func_name} error: {e}",
            )

    async def forcemerge_index(
        self,
        index_name: str,
        max_num_segments: int | None = None,
    ) -> Dict[str, Any]:
        try:
            params: Dict[str, Any] = {"index": index_name}
            if max_num_segments is not None:
                params["max_num_segments"] = max_num_segments

            return await self.es_client.indices.forcemerge(**params)
        except NotFoundError:
            raise BizException(
                status_code=HTTP_404_NOT_FOUND,
                message=f"Index {index_name} not found",
            )
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"{func_name} error: {e}",
            )

    async def delete_index(self, index_name: str) -> Dict[str, Any]:
        try:
            return await self.es_client.indices.delete(index=index_name)
        except NotFoundError:
            raise BizException(
                status_code=HTTP_404_NOT_FOUND,
                message=f"Index {index_name} not found",
            )
        except Exception as e:
            func_name = inspect.currentframe().f_code.co_name
            raise BizException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"{func_name} error: {e}",
            )

    @staticmethod
    def stringify_json(value: Any) -> str:
        if value is None:
            return ""

        if isinstance(value, str):
            return value

        return json.dumps(value, ensure_ascii=False, sort_keys=True)