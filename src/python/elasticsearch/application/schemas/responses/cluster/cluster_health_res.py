import logging
from pydantic import BaseModel, Field
from typing import Literal

logger = logging.getLogger(__name__)

class ClusterHealthRes(BaseModel):
    cluster_name: str                       = Field(..., description="클러스터 이름")
    status: Literal["green", "yellow", "red", "unknown", "unavailable"] \
                                            = Field(..., description="클러스터 health 상태")
    timed_out: bool                         = Field(..., description="지정된 timeout 내에 조건 충족 여부")
    number_of_nodes: int                    = Field(..., description="클러스터 노드 수")
    number_of_data_nodes: int               = Field(..., description="데이터 노드 수")
    active_primary_shards: int              = Field(..., description="active primary shard 개수")
    active_shards: int                      = Field(..., description="active primary + replica shard 총합")
    relocating_shards: int                  = Field(..., description="relocating 중인 shard 개수")
    initializing_shards: int                = Field(..., description="initializing 중인 shard 개수")
    unassigned_shards: int                  = Field(..., description="할당되지 않은 shard 개수")
    delayed_unassigned_shards: int          = Field(...,description="지연된 unassigned shard 개수")
    number_of_pending_tasks: int            = Field(...,description="대기 중인 cluster-level task 개수")
    number_of_in_flight_fetch: int          = Field(...,description="진행 중인 fetch operation 개수")
    active_shards_percent_as_number: float  = Field(...,description="전체 shard 대비 active shard 비율 (%)")