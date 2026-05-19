import logging
import time
from typing import Optional

from src.python.elasticsearch.application.repository.prometheus.prometheus_repository import PrometheusRepository
from src.python.elasticsearch.application.schemas.responses.metrics.metrics_response import (
    MetricPoint,
    MetricSeries,
    ClusterHealthSummary,
    ClusterOverviewResponse,
    NodeResourcesResponse,
    SearchPerformanceResponse,
    IndexingPerformanceResponse,
    CacheThreadPoolResponse,
    StorageOverviewResponse,
    NodeStorageInfo,
)
from src.python.elasticsearch.config.settings.env_settings import settings

logger = logging.getLogger(__name__)

# 시간 범위 → 초 변환 맵
TIME_RANGE_MAP: dict[str, int] = {
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "24h": 86400,
    "7d": 604800,
}

# 시간 범위별 자동 step 계산
STEP_MAP: dict[str, str] = {
    "15m": "15s",
    "1h": "30s",
    "6h": "120s",
    "24h": "300s",
    "7d": "1800s",
}


def _get_env_filter(env: Optional[str] = None) -> str:
    """APPLICATION_ACTIVE_PROFILE 또는 override로 env PromQL 필터 생성."""
    resolved_env = env or settings.APPLICATION_ACTIVE_PROFILE
    return f'env="{resolved_env}"'


def _resolve_time_params(time_range: str, step: Optional[str] = None) -> tuple[str, str, str]:
    """time_range 문자열에서 start/end/step을 계산."""
    now = time.time()
    seconds = TIME_RANGE_MAP.get(time_range, 3600)
    start = str(now - seconds)
    end = str(now)
    resolved_step = step or STEP_MAP.get(time_range, "60s")
    return start, end, resolved_step


def _parse_instant_results(data: dict) -> list[dict]:
    """Prometheus instant query 결과를 파싱."""
    return data.get("result", [])


def _parse_series(data: dict, metric_name: str) -> list[MetricSeries]:
    """Prometheus range query 결과를 MetricSeries 리스트로 변환."""
    results = data.get("result", [])
    series_list = []
    for result in results:
        labels = {k: v for k, v in result.get("metric", {}).items() if k != "__name__"}
        values = [
            MetricPoint(timestamp=float(v[0]), value=float(v[1]))
            for v in result.get("values", [])
        ]
        series_list.append(MetricSeries(
            metric_name=metric_name,
            labels=labels,
            values=values,
        ))
    return series_list


def _parse_instant_scalar(results: list[dict], metric_name: str, default: float = 0) -> float:
    """instant query 결과에서 특정 메트릭의 첫 번째 값 추출."""
    for r in results:
        if r.get("metric", {}).get("__name__") == metric_name:
            return float(r["value"][1])
    return default


def _sum_instant_values(results: list[dict], metric_name: str) -> float:
    """instant query 결과에서 특정 메트릭의 모든 노드 값 합산."""
    total = 0.0
    for r in results:
        if r.get("metric", {}).get("__name__") == metric_name:
            total += float(r["value"][1])
    return total


class MetricsService:
    """Prometheus 메트릭 조회 비즈니스 로직."""

    def __init__(self, prometheus_repo: Optional[PrometheusRepository] = None):
        self.prom = prometheus_repo or PrometheusRepository()

    async def get_cluster_overview(self, env: Optional[str] = None) -> ClusterOverviewResponse:
        """클러스터 헬스 + 노드/샤드/문서 요약 (instant query)."""
        env_filter = _get_env_filter(env)

        data = await self.prom.query(f'{{__name__=~"elasticsearch_cluster_health_.*|elasticsearch_indices_docs|elasticsearch_indices_store_size_bytes",{env_filter}}}')
        results = _parse_instant_results(data)

        # 클러스터 상태 (color 라벨로 판단)
        status = "unknown"
        for r in results:
            if r.get("metric", {}).get("__name__") == "elasticsearch_cluster_health_status":
                val = float(r["value"][1])
                color = r.get("metric", {}).get("color", "")
                if val == 1.0 and color:
                    status = color

        health = ClusterHealthSummary(
            status=status,
            number_of_nodes=int(_parse_instant_scalar(results, "elasticsearch_cluster_health_number_of_nodes")),
            number_of_data_nodes=int(_parse_instant_scalar(results, "elasticsearch_cluster_health_number_of_data_nodes")),
            active_shards=int(_parse_instant_scalar(results, "elasticsearch_cluster_health_active_shards")),
            unassigned_shards=int(_parse_instant_scalar(results, "elasticsearch_cluster_health_unassigned_shards")),
            relocating_shards=int(_parse_instant_scalar(results, "elasticsearch_cluster_health_relocating_shards")),
            initializing_shards=int(_parse_instant_scalar(results, "elasticsearch_cluster_health_initializing_shards")),
            pending_tasks=int(_parse_instant_scalar(results, "elasticsearch_cluster_health_number_of_pending_tasks")),
            total_docs=_sum_instant_values(results, "elasticsearch_indices_docs"),
            total_store_size_bytes=_sum_instant_values(results, "elasticsearch_indices_store_size_bytes"),
        )

        return ClusterOverviewResponse(health=health)

    async def get_node_resources(
        self, env: Optional[str] = None, time_range: str = "1h", step: Optional[str] = None
    ) -> NodeResourcesResponse:
        """노드별 CPU/메모리/JVM/GC 시계열."""
        env_filter = _get_env_filter(env)
        start, end, resolved_step = _resolve_time_params(time_range, step)

        cpu_data = await self.prom.query_range(
            f'elasticsearch_os_cpu_percent{{{env_filter}}}', start, end, resolved_step
        )
        mem_data = await self.prom.query_range(
            f'elasticsearch_os_mem_used_bytes{{{env_filter}}}', start, end, resolved_step
        )
        jvm_used_data = await self.prom.query_range(
            f'elasticsearch_jvm_memory_used_bytes{{{env_filter},area="heap"}}', start, end, resolved_step
        )
        jvm_max_data = await self.prom.query_range(
            f'elasticsearch_jvm_memory_max_bytes{{{env_filter},area="heap"}}', start, end, resolved_step
        )
        gc_count_data = await self.prom.query_range(
            f'rate(elasticsearch_jvm_gc_collection_seconds_count{{{env_filter}}}[5m])', start, end, resolved_step
        )
        gc_time_data = await self.prom.query_range(
            f'rate(elasticsearch_jvm_gc_collection_seconds_sum{{{env_filter}}}[5m])', start, end, resolved_step
        )

        return NodeResourcesResponse(
            cpu_percent=_parse_series(cpu_data, "cpu_percent"),
            memory_used_bytes=_parse_series(mem_data, "memory_used_bytes"),
            jvm_heap_used_bytes=_parse_series(jvm_used_data, "jvm_heap_used_bytes"),
            jvm_heap_max_bytes=_parse_series(jvm_max_data, "jvm_heap_max_bytes"),
            gc_collection_count=_parse_series(gc_count_data, "gc_collection_count"),
            gc_collection_time=_parse_series(gc_time_data, "gc_collection_time"),
        )

    async def get_search_performance(
        self, env: Optional[str] = None, time_range: str = "1h", step: Optional[str] = None
    ) -> SearchPerformanceResponse:
        """검색 성능 시계열 (rate 기반)."""
        env_filter = _get_env_filter(env)
        start, end, resolved_step = _resolve_time_params(time_range, step)

        query_rate_data = await self.prom.query_range(
            f'rate(elasticsearch_indices_search_query_total{{{env_filter}}}[5m])', start, end, resolved_step
        )
        query_time_data = await self.prom.query_range(
            f'rate(elasticsearch_indices_search_query_time_seconds{{{env_filter}}}[5m])', start, end, resolved_step
        )
        fetch_rate_data = await self.prom.query_range(
            f'rate(elasticsearch_indices_search_fetch_total{{{env_filter}}}[5m])', start, end, resolved_step
        )
        fetch_time_data = await self.prom.query_range(
            f'rate(elasticsearch_indices_search_fetch_time_seconds{{{env_filter}}}[5m])', start, end, resolved_step
        )

        return SearchPerformanceResponse(
            query_rate=_parse_series(query_rate_data, "query_rate"),
            query_latency=_parse_series(query_time_data, "query_latency"),
            fetch_rate=_parse_series(fetch_rate_data, "fetch_rate"),
            fetch_latency=_parse_series(fetch_time_data, "fetch_latency"),
        )

    async def get_indexing_performance(
        self, env: Optional[str] = None, time_range: str = "1h", step: Optional[str] = None
    ) -> IndexingPerformanceResponse:
        """인덱싱 성능 시계열 (rate 기반)."""
        env_filter = _get_env_filter(env)
        start, end, resolved_step = _resolve_time_params(time_range, step)

        index_rate_data = await self.prom.query_range(
            f'rate(elasticsearch_indices_indexing_index_total{{{env_filter}}}[5m])', start, end, resolved_step
        )
        index_time_data = await self.prom.query_range(
            f'rate(elasticsearch_indices_indexing_index_time_seconds_total{{{env_filter}}}[5m])', start, end, resolved_step
        )
        delete_rate_data = await self.prom.query_range(
            f'rate(elasticsearch_indices_indexing_delete_total{{{env_filter}}}[5m])', start, end, resolved_step
        )

        return IndexingPerformanceResponse(
            index_rate=_parse_series(index_rate_data, "index_rate"),
            index_latency=_parse_series(index_time_data, "index_latency"),
            delete_rate=_parse_series(delete_rate_data, "delete_rate"),
        )

    async def get_cache_threadpool(
        self, env: Optional[str] = None, time_range: str = "1h", step: Optional[str] = None
    ) -> CacheThreadPoolResponse:
        """캐시 및 스레드풀 메트릭 시계열."""
        env_filter = _get_env_filter(env)
        start, end, resolved_step = _resolve_time_params(time_range, step)

        cache_size = await self.prom.query_range(
            f'elasticsearch_indices_query_cache_memory_size_bytes{{{env_filter}}}', start, end, resolved_step
        )
        cache_evictions = await self.prom.query_range(
            f'rate(elasticsearch_indices_query_cache_evictions{{{env_filter}}}[5m])', start, end, resolved_step
        )
        tp_active = await self.prom.query_range(
            f'elasticsearch_thread_pool_active_count{{{env_filter},type=~"search|write|index"}}', start, end, resolved_step
        )
        tp_rejected = await self.prom.query_range(
            f'rate(elasticsearch_thread_pool_rejected_count{{{env_filter},type=~"search|write|index"}}[5m])', start, end, resolved_step
        )
        tp_queue = await self.prom.query_range(
            f'elasticsearch_thread_pool_queue_count{{{env_filter},type=~"search|write|index"}}', start, end, resolved_step
        )

        return CacheThreadPoolResponse(
            query_cache_size=_parse_series(cache_size, "query_cache_size"),
            query_cache_evictions=_parse_series(cache_evictions, "query_cache_evictions"),
            thread_pool_active=_parse_series(tp_active, "thread_pool_active"),
            thread_pool_rejected=_parse_series(tp_rejected, "thread_pool_rejected"),
            thread_pool_queue=_parse_series(tp_queue, "thread_pool_queue"),
        )

    async def get_storage_overview(self, env: Optional[str] = None) -> StorageOverviewResponse:
        """노드별 스토리지 사용률 (instant query)."""
        env_filter = _get_env_filter(env)

        data = await self.prom.query(
            f'{{__name__=~"elasticsearch_filesystem_data_available_bytes|elasticsearch_filesystem_data_size_bytes",{env_filter}}}'
        )
        results = _parse_instant_results(data)

        # 노드별 집계
        node_map: dict[str, dict[str, float]] = {}
        for r in results:
            metric = r.get("metric", {})
            node_name = metric.get("name", "") or metric.get("node", "unknown")
            metric_name = metric.get("__name__", "")
            value = float(r["value"][1])

            if node_name not in node_map:
                node_map[node_name] = {"total": 0, "available": 0}

            if "size_bytes" in metric_name:
                node_map[node_name]["total"] = value
            elif "available_bytes" in metric_name:
                node_map[node_name]["available"] = value

        nodes = []
        for name, info in node_map.items():
            total = info["total"]
            available = info["available"]
            used = total - available
            used_percent = (used / total * 100) if total > 0 else 0
            nodes.append(NodeStorageInfo(
                node_name=name,
                total_bytes=total,
                available_bytes=available,
                used_bytes=used,
                used_percent=round(used_percent, 2),
            ))

        # 사용률 높은 순으로 정렬
        nodes.sort(key=lambda n: n.used_percent, reverse=True)

        return StorageOverviewResponse(nodes=nodes)
