from typing import Dict, Any
from collections import defaultdict

from src.python.elasticsearch.application.repository.elasticsearch.entities.cat_indices_entity import IndicesEntity
from src.python.elasticsearch.application.repository.elasticsearch.entities.cat_shard_entity import ShardsEntity
from src.python.elasticsearch.application.repository.elasticsearch.entities.nodes_entity import NodesEntity
from src.python.elasticsearch.application.schemas.responses.indices.indices_placement_res import IndicesPlacementRes, \
    NodeViewRes, ShardPlacementRes, IndexPlacementRes


class IndicesPlacementMapper:

    @staticmethod
    def to_response(master_node_id: str,
                    nodes_infos: NodesEntity,
                    shards_infos: ShardsEntity,
                    indices_infos: IndicesEntity
                    ) -> IndicesPlacementRes:
        """
        Map ClusterHealthEntity → ClusterHealthRes
        """
        # 1) 노드 정보 정규화 (좌측 리스트)
        nodes = []
        for node_id, node in nodes_infos.nodes.items():
            node = NodeViewRes(
                id=node_id,
                name=node.name,
                host=f"{node.ip}:{node.settings.get('http', {}).get('port')}",
                roles=node.roles,
                is_master=node_id == master_node_id,
            )
            nodes.append(node)

        nodes.sort(key=lambda node: node.name)

        node_id_to_name_map = {nid: n.name for nid, n in nodes_infos.nodes.items()}
        index_status_map = {idx.index: idx.status for idx in indices_infos.indices}

        # 2) 인덱스별 shard 그룹핑
        indices_map: Dict[str, IndexPlacementRes] = {}
        has_unassigned_shards = False

        for shard in shards_infos.shards:
            index_name = shard.index

            if index_name not in indices_map:
                indices_map[index_name] = IndexPlacementRes(
                    index=index_name,
                    status=index_status_map.get(index_name, "close"),
                    shards_by_node=defaultdict(list),
                    unassigned=[]
                )

            # 화면에 쓸 shard 요약 정보
            shard_repr = ShardPlacementRes(
                shard=shard.shard,
                prirep=shard.prirep,  # 'p' / 'r'
                state=shard.state,  # STARTED / UNASSIGNED 등
                node_id=shard.id,  # ES node id
                node_name=shard.node,  # ES node name (string)
                store=shard.store,
                docs=shard.docs
            )

            # 3) UNASSIGNED(미할당) 처리
            # state 이름이 'UNASSIGNED'이거나 node_id가 없는 경우
            if str(shard.state).upper() == "UNASSIGNED" or not shard.id or shard.id not in node_id_to_name_map:
                indices_map[index_name].unassigned.append(shard_repr)
                has_unassigned_shards = True
            else:
                indices_map[index_name].shards_by_node[nodes_infos.nodes[shard.id].name] = shard_repr

        # 4) indices를 리스트로 (정렬은 원하는 기준대로)
        indices = list(indices_map.values())
        indices.sort(key=lambda x: x.index)

        return IndicesPlacementRes(
            nodes=nodes,
            indices=indices,
            has_unassigned_shards=has_unassigned_shards
        )