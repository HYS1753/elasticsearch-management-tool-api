import logging
from pydantic import BaseModel, Field
from typing import Optional, List

logger = logging.getLogger(__name__)

class NodeStatusesRes(BaseModel):
    # docs / store
    docs_count: int = Field(..., description="문서 개수")
    docs_deleted: int = Field(..., description="삭제된 문서 개수")
    docs_store_size: str = Field(..., description="샤드 스토어 총 용량")

    # OS CPU
    os_cpu_percent: int = Field(..., description="노드 CPU 사용율")
    os_cpu_load_average_1m: float = Field(..., description="노드 CPU 1분 평균 사용율")
    os_cpu_load_average_5m: float = Field(..., description="노드 CPU 5분 평균 사용율")
    os_cpu_load_average_15m: float = Field(..., description="노드 CPU 15분 평균 사용율")

    # OS 메모리
    os_mem_total: str = Field(..., description="노드 OS 메모리 총량")
    os_mem_used: str = Field(..., description="노드 OS 사용 메모리")
    os_mem_used_percent: int = Field(..., description="노드 OS 사용 메모리 비율(%)")
    os_mem_free: str = Field(..., description="노드 OS 남은 메모리")

    # JVM 메모리
    jvm_heap_used: str = Field(..., description="JVM heap 사용량")
    jvm_heap_used_percent: int = Field(..., description="JVM heap 사용 비율(%)")
    jvm_heap_max: str = Field(..., description="JVM heap 최대 크기")

    # 파일시스템
    fs_total: str = Field(..., description="FS 총 용량")
    fs_free: str = Field(..., description="FS 남은 용량")
    fs_used: str = Field(..., description="FS 사용 용량")
    fs_used_percent: int = Field(..., description="FS 사용 용량 비율(%)")

    # 검색 thread pool
    search_threads: int = Field(..., description="search thread 개수")
    search_queue: int = Field(..., description="search thread pool queue 길이")
    search_active: int = Field(..., description="현재 실행 중인 search 작업 수")
    search_rejected: int = Field(..., description="거절된 search 작업 수 (누적)")
    search_completed: int = Field(..., description="완료된 search 작업 수 (누적)")

    # 인덱싱 pressure
    indexing_current_all: str = Field(..., description="현재 인덱싱 메모리 사용량")
    indexing_total_all: str = Field(..., description="누적 인덱싱 메모리 사용량")
    indexing_limit: str = Field(..., description="인덱싱 메모리 limit")
    indexing_pressure_percent: float = Field(..., description="현재 인덱싱 pressure 비율 (%)")
    indexing_rejections_total: int = Field(..., description="인덱싱 관련 전체 rejection 수 합계")

class NodeStatusRes(BaseModel):
    is_master_node: bool = Field(..., description="현재 마스터 노드 여부")
    id: str = Field(..., description="노드 ID")
    name: str = Field(..., description="노드 이름")
    host: str = Field(..., description="HTTP 호스트 (ip:port)")
    transport: str = Field(..., description="Transport 주소 (ip:port)")
    roles: List[str] = Field(..., description="노드 역할 목록")
    stats: Optional[NodeStatusesRes] = Field(
        None,
        description="노드 통계 정보 (노드 stats 조회 실패 시 None)"
    )

class NodesStatusRes(BaseModel):
    nodes: List[NodeStatusRes] = Field(..., description="클러스터 내 노드 목록")