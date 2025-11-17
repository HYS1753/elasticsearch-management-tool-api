from typing import Dict, List, Optional

from src.python.elasticsearch.application.repository.elasticsearch.entities.nodes_entity import NodesEntity
from src.python.elasticsearch.application.repository.elasticsearch.entities.nodes_stats_entity import NodesStatsEntity
from src.python.elasticsearch.application.schemas.responses.cluster.node_status_res import NodeStatusRes, NodesStatusRes, NodeStatusesRes
from src.python.elasticsearch.common.utils.formatter import format_bytes


class NodeStatusMapper:
    @staticmethod
    def sort_roles(roles: list[str]) -> list[str]:
        ROLE_PRIORITY = [
            "master",
            "data",
            "ingest",
            "ml",
            "transform",
            "remote_cluster_client",
            "data_hot",
            "data_warm",
            "data_content",
            "data_cold",
            "data_frozen"
        ]
        return sorted(
            roles,
            key=lambda r: (
                ROLE_PRIORITY.index(r) if r in ROLE_PRIORITY else 999,
                r  # priority 없는 것들은 알파벳 순 정렬
            )
        )

    @staticmethod
    def to_response(
        master_node_id: str,
        nodes_entity: NodesEntity,
        nodes_stats: Dict[str, NodesStatsEntity],
    ) -> NodesStatusRes:
        nodes: List[NodeStatusRes] = []

        for node_id, node in nodes_entity.nodes.items():
            is_master_node = (master_node_id == node_id)

            # host(ip:port) 구성
            host_ip = node.ip
            host_port = node.settings.get("http", {}).get("port", "")
            host = f"{host_ip}:{host_port}" if host_ip and host_port else host_ip

            # 기본값 (stats 없을 수도 있으니 robust하게)
            stats_res: Optional[NodeStatusesRes] = None

            stats_entity = nodes_stats.get(node_id)
            if stats_entity is not None:
                # NodesStatsEntity.nodes 안에 다시 node_id 키로 NodeStatEntity 가 들어있음
                node_stat = stats_entity.nodes.get(node_id)
                if node_stat is not None:
                    # indices.docs
                    docs = (node_stat.indices or {}).get("docs", {})
                    docs_count = docs.get("count", 0)
                    docs_deleted = docs.get("deleted", 0)
                    docs_store_size = format_bytes(docs.get("total_size_in_bytes", 0))

                    # os.cpu
                    os_cpu = (node_stat.os or {}).get("cpu", {})
                    os_cpu_percent = os_cpu.get("percent", 0)
                    os_cpu_load_average = os_cpu.get("load_average", {})
                    os_cpu_load_average_1m = os_cpu_load_average.get("1m", 0.0)
                    os_cpu_load_average_5m = os_cpu_load_average.get("5m", 0.0)
                    os_cpu_load_average_15m = os_cpu_load_average.get("15m", 0.0)

                    # os.mem
                    os_mem = (node_stat.os or {}).get("mem", {})
                    os_mem_total = format_bytes(os_mem.get("total_in_bytes", 0))
                    os_mem_used = format_bytes(os_mem.get("used_in_bytes", 0))
                    os_mem_used_percent = os_mem.get("used_percent", 0)
                    os_mem_free = format_bytes(os_mem.get("free_in_bytes", 0))

                    # jvm.mem
                    jvm_mem = (node_stat.jvm or {}).get("mem", {})
                    jvm_heap_used = format_bytes(jvm_mem.get("heap_used_in_bytes", 0))
                    jvm_heap_used_percent = jvm_mem.get("heap_used_percent", 0)
                    jvm_heap_max = format_bytes(jvm_mem.get("heap_max_in_bytes", 0))

                    # fs.total
                    fs_total = (node_stat.fs or {}).get("total", {})
                    fs_total_in_bytes = fs_total.get("total_in_bytes", 0)
                    fs_total_str = format_bytes(fs_total_in_bytes)
                    fs_free_in_bytes = fs_total.get("free_in_bytes", 0)
                    fs_free_str = format_bytes(fs_free_in_bytes)
                    fs_used_in_bytes = fs_total_in_bytes - fs_free_in_bytes
                    fs_used_str = format_bytes(fs_used_in_bytes)
                    if fs_total_in_bytes > 0:
                        fs_used_percent = int(fs_used_in_bytes / fs_total_in_bytes * 100)
                    else:
                        fs_used_percent = 0


                    # thread_pool.search
                    tp_search = (node_stat.thread_pool or {}).get("search", {})
                    search_threads = tp_search.get("threads", 0)
                    search_queue = tp_search.get("queue", 0)
                    search_active = tp_search.get("active", 0)
                    search_rejected = tp_search.get("rejected", 0)
                    search_completed = tp_search.get("completed", 0)

                    # indexing_pressure.memory
                    indexing_mem = (node_stat.indexing_pressure or {}).get("memory", {})
                    current = indexing_mem.get("current", {})
                    total = indexing_mem.get("total", {})
                    indexing_total_all = format_bytes(total.get("all_in_bytes", 0))
                    limit_bytes = indexing_mem.get("limit_in_bytes", 0)
                    limit_bytes_str = format_bytes(limit_bytes)
                    indexing_current_all = current.get("all_in_bytes", 0)
                    indexing_current_all_str = format_bytes(indexing_current_all)

                    # rejections 합산
                    coord_rej = total.get("coordinating_rejections", 0)
                    primary_rej = total.get("primary_rejections", 0)
                    replica_rej = total.get("replica_rejections", 0)
                    primary_doc_rej = total.get("primary_document_rejections", 0)
                    indexing_rejections_total = (
                        coord_rej + primary_rej + replica_rej + primary_doc_rej
                    )

                    # pressure %
                    if limit_bytes > 0:
                        indexing_pressure_percent = round(
                            indexing_current_all / limit_bytes * 100, 2
                        )
                    else:
                        indexing_pressure_percent = 0.0

                    stats_res = NodeStatusesRes(
                        docs_count=docs_count,
                        docs_deleted=docs_deleted,
                        docs_store_size=docs_store_size,
                        os_cpu_percent=os_cpu_percent,
                        os_cpu_load_average_1m=os_cpu_load_average_1m,
                        os_cpu_load_average_5m=os_cpu_load_average_5m,
                        os_cpu_load_average_15m=os_cpu_load_average_15m,
                        os_mem_total=os_mem_total,
                        os_mem_used=os_mem_used,
                        os_mem_used_percent=os_mem_used_percent,
                        os_mem_free=os_mem_free,
                        jvm_heap_used=jvm_heap_used,
                        jvm_heap_used_percent=jvm_heap_used_percent,
                        jvm_heap_max=jvm_heap_max,
                        fs_total=fs_total_str,
                        fs_free=fs_free_str,
                        fs_used=fs_used_str,
                        fs_used_percent=fs_used_percent,
                        search_threads=search_threads,
                        search_queue=search_queue,
                        search_active=search_active,
                        search_rejected=search_rejected,
                        search_completed=search_completed,
                        indexing_current_all=indexing_current_all_str,
                        indexing_total_all=indexing_total_all,
                        indexing_limit=limit_bytes_str,
                        indexing_pressure_percent=indexing_pressure_percent,
                        indexing_rejections_total=indexing_rejections_total,
                    )

            nodes.append(
                NodeStatusRes(
                    is_master_node=is_master_node,
                    id=node_id,
                    name=node.name,
                    host=host,
                    transport=node.transport_address,
                    roles=NodeStatusMapper.sort_roles(node.roles),
                    stats=stats_res,
                )
            )

        nodes_sorted = sorted(nodes, key=lambda x: x.name)

        return NodesStatusRes(nodes=nodes_sorted)