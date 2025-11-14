from elasticsearch import AsyncElasticsearch
from fastapi import FastAPI


class ElasticsearchClusterRepository:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def get_health(self, params: dict) -> dict:
        return await self.es_client.cluster.health(**params)