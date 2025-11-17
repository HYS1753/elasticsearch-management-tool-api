from src.python.elasticsearch.application.repository.elasticsearch.entities.cluster_health_entity import \
    ClusterHealthEntity
from src.python.elasticsearch.application.schemas.responses.cluster.cluster_health_res import ClusterHealthRes


class ClusterStateMapper:

    @staticmethod
    def to_response(entity: ClusterHealthEntity) -> ClusterHealthRes:
        """
        Map ClusterHealthEntity → ClusterHealthRes
        """
        return ClusterHealthRes(
            cluster_name=entity.cluster_name,
            status=entity.status if entity.status in ["green", "yellow", "red"] else "unknown",
            timed_out=entity.timed_out,
            number_of_nodes=entity.number_of_nodes,
            number_of_data_nodes=entity.number_of_data_nodes,
            active_primary_shards=entity.active_primary_shards,
            active_shards=entity.active_shards,
            relocating_shards=entity.relocating_shards,
            initializing_shards=entity.initializing_shards,
            unassigned_shards=entity.unassigned_shards,
            delayed_unassigned_shards=entity.delayed_unassigned_shards,
            number_of_pending_tasks=entity.number_of_pending_tasks,
            number_of_in_flight_fetch=entity.number_of_in_flight_fetch,
            active_shards_percent_as_number=entity.active_shards_percent_as_number,
        )