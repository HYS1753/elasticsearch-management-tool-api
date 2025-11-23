import logging

from elasticsearch import AsyncElasticsearch

from src.python.elasticsearch.application.repository.elasticsearch.cat_repository import ElasticsearchCatRepository
from src.python.elasticsearch.application.repository.elasticsearch.nodes_repository import ElasticsearchNodesRepository
from src.python.elasticsearch.application.schemas.responses.indices.indices_placement_res import IndicesPlacementRes
from src.python.elasticsearch.application.schemas.responses.indices.indices_res import IndicesRes
from src.python.elasticsearch.application.services.mapper.indices_placement_mapper import IndicesPlacementMapper
from src.python.elasticsearch.application.services.mapper.indices_mapper import IndicesMapper

logger = logging.getLogger(__name__)

class IndicesService:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def indices(self,
                      include_hidden_index: bool = False,
                      include_closed_index: bool = False
                      ) -> IndicesRes:
        # 1. Repository 정의
        cat_repository = ElasticsearchCatRepository(self.es_client)

        # 2. ES 호출
        indices_infos = await cat_repository.get_indices_info(exclude_hidden=(not include_hidden_index))

        # 3. 닫힌 인덱스 제외 처리
        if not include_closed_index:
            filtered_indices = [
                index for index in indices_infos.indices
                if index.status != "close"
            ]
            indices_infos.indices = filtered_indices

        return IndicesMapper.to_response(indices_infos)

    async def indices_placement(self,
                                include_hidden_index: bool = False,
                                include_closed_index: bool = False
                                ) -> IndicesPlacementRes:
        # 1. Respository 정의
        cat_repository = ElasticsearchCatRepository(self.es_client)
        nodes_repository = ElasticsearchNodesRepository(self.es_client)

        # 2. ES 호출
        master_node_id = await cat_repository.get_master_node()
        nodes_infos = await nodes_repository.get_nodes()
        shards_infos = await cat_repository.get_shards_info(exclude_hidden=(not include_hidden_index))
        indices_infos = await cat_repository.get_indices_info(exclude_hidden=(not include_hidden_index))

        # 3. 닫힌 인덱스 제외 처리
        if not include_closed_index:
            closed_indexes = {
                idx.index
                for idx in indices_infos.indices
                if idx.status == "close"
            }
            filtered_shards = [
                shard for shard in shards_infos.shards
                if shard.index not in closed_indexes
            ]
            shards_infos.shards = filtered_shards

        # 3. Mapper 호출 및 응답 반환
        return IndicesPlacementMapper.to_response(
            master_node_id=master_node_id,
            nodes_infos=nodes_infos,
            shards_infos=shards_infos,
            indices_infos=indices_infos
        )

