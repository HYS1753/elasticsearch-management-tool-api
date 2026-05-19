from pydantic import BaseModel, Field
from typing import Any, Optional


class MetricPoint(BaseModel):
    """단일 시계열 데이터 포인트."""
    timestamp: float = Field(..., description="Unix timestamp")
    value: float = Field(..., description="메트릭 값")


class MetricSeries(BaseModel):
    """라벨이 붙은 시계열 데이터."""
    metric_name: str = Field(..., description="메트릭 이름")
    labels: dict[str, str] = Field(default_factory=dict, description="Prometheus 라벨")
    values: list[MetricPoint] = Field(default_factory=list, description="데이터 포인트 목록")


# ──────────────────────────────────────────────
# Cluster Overview (instant)
# ──────────────────────────────────────────────

class ClusterHealthSummary(BaseModel):
    """클러스터 전반 헬스 요약."""
    status: str = Field("unknown", description="green/yellow/red")
    number_of_nodes: int = 0
    number_of_data_nodes: int = 0
    active_shards: int = 0
    unassigned_shards: int = 0
    relocating_shards: int = 0
    initializing_shards: int = 0
    pending_tasks: int = 0
    total_docs: float = 0
    total_store_size_bytes: float = 0


class ClusterOverviewResponse(BaseModel):
    health: ClusterHealthSummary = Field(default_factory=ClusterHealthSummary)


# ──────────────────────────────────────────────
# Node Resources (range)
# ──────────────────────────────────────────────

class NodeResourcesResponse(BaseModel):
    cpu_percent: list[MetricSeries] = Field(default_factory=list)
    memory_used_bytes: list[MetricSeries] = Field(default_factory=list)
    jvm_heap_used_bytes: list[MetricSeries] = Field(default_factory=list)
    jvm_heap_max_bytes: list[MetricSeries] = Field(default_factory=list)
    gc_collection_count: list[MetricSeries] = Field(default_factory=list)
    gc_collection_time: list[MetricSeries] = Field(default_factory=list)


# ──────────────────────────────────────────────
# Search Performance (range)
# ──────────────────────────────────────────────

class SearchPerformanceResponse(BaseModel):
    query_rate: list[MetricSeries] = Field(default_factory=list)
    query_latency: list[MetricSeries] = Field(default_factory=list)
    fetch_rate: list[MetricSeries] = Field(default_factory=list)
    fetch_latency: list[MetricSeries] = Field(default_factory=list)


# ──────────────────────────────────────────────
# Indexing Performance (range)
# ──────────────────────────────────────────────

class IndexingPerformanceResponse(BaseModel):
    index_rate: list[MetricSeries] = Field(default_factory=list)
    index_latency: list[MetricSeries] = Field(default_factory=list)
    delete_rate: list[MetricSeries] = Field(default_factory=list)


# ──────────────────────────────────────────────
# Cache & Thread Pool (range)
# ──────────────────────────────────────────────

class CacheThreadPoolResponse(BaseModel):
    query_cache_size: list[MetricSeries] = Field(default_factory=list)
    query_cache_evictions: list[MetricSeries] = Field(default_factory=list)
    thread_pool_active: list[MetricSeries] = Field(default_factory=list)
    thread_pool_rejected: list[MetricSeries] = Field(default_factory=list)
    thread_pool_queue: list[MetricSeries] = Field(default_factory=list)


# ──────────────────────────────────────────────
# Storage Overview (instant)
# ──────────────────────────────────────────────

class NodeStorageInfo(BaseModel):
    node_name: str = ""
    total_bytes: float = 0
    available_bytes: float = 0
    used_bytes: float = 0
    used_percent: float = 0


class StorageOverviewResponse(BaseModel):
    nodes: list[NodeStorageInfo] = Field(default_factory=list)
