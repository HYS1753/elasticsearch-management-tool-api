from typing import Any, Dict
from elasticsearch import AsyncElasticsearch


class ElasticsearchSearchExaplainRepository:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def search_with_explain(
        self,
        index: str | list[str],
        body: Dict[str, Any]
    ) -> Dict[str, Any]:
        req_body = dict(body)
        req_body["explain"] = True
        return await self.es_client.search(
            index=index,
            body=req_body
        )

    async def explain_document(
        self,
        index: str,
        doc_id: str,
        body: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await self.es_client.explain(
            index=index,
            id=doc_id,
            body=body
        )