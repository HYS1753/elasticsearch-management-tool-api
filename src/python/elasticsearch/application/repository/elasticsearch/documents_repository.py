import inspect
from typing import Any

from elasticsearch import AsyncElasticsearch, NotFoundError
from pydantic import ValidationError
from starlette.status import HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR

from src.python.elasticsearch.config.exceptions.biz_exceptions import BizException


class ElasticsearchDocumentsRepository:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def search_documents(
        self,
        index_name: str,
        query: dict[str, Any] | None = None,
        from_: int = 0,
        size: int = 20,
        sort: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        try:
            body: dict[str, Any] = {
                "query": query or {"match_all": {}},
                "from": from_,
                "size": size,
            }

            if sort:
                filtered_sort = [
                    item for item in sort
                    if "_id" not in item
                ]

                if filtered_sort:
                    body["sort"] = filtered_sort

            response = await self.es_client.search(
                index=index_name,
                body=body,
            )

            if hasattr(response, "body"):
                return response.body

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