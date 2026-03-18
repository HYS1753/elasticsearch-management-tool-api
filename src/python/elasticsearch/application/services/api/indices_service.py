import logging

from elasticsearch import AsyncElasticsearch

from src.python.elasticsearch.application.repository.elasticsearch.cat_repository import ElasticsearchCatRepository
from src.python.elasticsearch.application.repository.elasticsearch.indices_repository import ElasticsearchIndicesRepository
from src.python.elasticsearch.application.repository.elasticsearch.nodes_repository import ElasticsearchNodesRepository
from src.python.elasticsearch.application.schemas.responses.indices.index_detail_res import IndexDetailRes
from src.python.elasticsearch.application.schemas.responses.indices.indices_placement_res import IndicesPlacementRes
from src.python.elasticsearch.application.schemas.responses.indices.indices_res import IndicesRes
from src.python.elasticsearch.application.services.mapper.index_detail_mapper import IndexDetailMapper
from src.python.elasticsearch.application.services.mapper.indices_mapper import IndicesMapper
from src.python.elasticsearch.application.services.mapper.indices_placement_mapper import IndicesPlacementMapper

logger = logging.getLogger(__name__)


class IndicesService:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def indices(
        self,
        include_hidden_index: bool = False,
        include_closed_index: bool = False
    ) -> IndicesRes:
        cat_repository = ElasticsearchCatRepository(self.es_client)

        indices_infos = await cat_repository.get_indices_info(
            exclude_hidden=(not include_hidden_index)
        )

        if not include_closed_index:
            filtered_indices = [
                index for index in indices_infos.indices
                if index.status != "close"
            ]
            indices_infos.indices = filtered_indices

        return IndicesMapper.to_response(indices_infos)

    async def index_detail(self, index_name: str) -> IndexDetailRes:
        cat_repository = ElasticsearchCatRepository(self.es_client)
        indices_repository = ElasticsearchIndicesRepository(self.es_client)

        index_info = await cat_repository.get_index_info(index_name=index_name)
        settings_response = await indices_repository.get_index_settings(index_name=index_name)
        mappings_response = await indices_repository.get_index_mappings(index_name=index_name)
        aliases_response = await indices_repository.get_index_aliases(index_name=index_name)
        stats_response = await indices_repository.get_index_stats(index_name=index_name)

        return IndexDetailMapper.to_response(
            index_info=index_info,
            settings_response=settings_response,
            mappings_response=mappings_response,
            aliases_response=aliases_response,
            stats_response=stats_response,
        )

    async def indices_placement(
        self,
        include_hidden_index: bool = False,
        include_closed_index: bool = False
    ) -> IndicesPlacementRes:
        cat_repository = ElasticsearchCatRepository(self.es_client)
        nodes_repository = ElasticsearchNodesRepository(self.es_client)

        master_node_id = await cat_repository.get_master_node()
        nodes_infos = await nodes_repository.get_nodes()
        shards_infos = await cat_repository.get_shards_info(
            exclude_hidden=(not include_hidden_index)
        )
        indices_infos = await cat_repository.get_indices_info(
            exclude_hidden=(not include_hidden_index)
        )

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

        return IndicesPlacementMapper.to_response(
            master_node_id=master_node_id,
            nodes_infos=nodes_infos,
            shards_infos=shards_infos,
            indices_infos=indices_infos,
        )