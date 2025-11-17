from src.python.elasticsearch.application.repository.elasticsearch.entities.cluster_health_entity import \
    ClusterHealthEntity
from src.python.elasticsearch.application.repository.elasticsearch.entities.nodes_entity import ClusterNodesEntity
from src.python.elasticsearch.application.schemas.responses.cluster.cluster_health_res import ClusterHealthRes
from src.python.elasticsearch.application.schemas.responses.cluster.cluster_nodes_res import ClusterNodesRes, ClusterNodeRes


class ClusterNodesMapper:

    @staticmethod
    def to_response(entity: ClusterNodesEntity, master_node_id: str) -> ClusterNodesRes:
        """
        Map ClusterNodesEntity, MasterNodeId  → ClusterNodesRes
        """
        nodes = []
        for key, value in entity.nodes.items():
            is_master_node = (master_node_id == key)
            host_ip = value.ip
            host_port = value.settings.get("http", {}).get("port", "")
            host = f"{host_ip}:{host_port}" if host_ip and host_port else host_ip
            nodes.append(ClusterNodeRes(
                is_master_node=is_master_node,
                id=key,
                name=value.name,
                host=host,
                transport=value.transport_address,
                roles=value.roles
            ))

        nodes_sorted = sorted(nodes, key=lambda x: x.name)

        return ClusterNodesRes(
            nodes= nodes_sorted
        )
