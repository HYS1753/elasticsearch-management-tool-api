from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class IndexSettingsEntity(BaseModel):
    # 기본 샤드/레플리카
    number_of_shards: Optional[int] = Field(None, title="Primary shard count")
    number_of_replicas: Optional[int] = Field(None, title="Replica shard count")

    # 자주 보는 튜닝 값들
    refresh_interval: Optional[str] = Field(None, title="Refresh interval (e.g. 1s)")
    max_result_window: Optional[int] = Field(None, title="Max result window")

    # 메타 정보
    creation_date: Optional[str] = Field(None, title="Index creation timestamp (epoch millis as string)")
    provided_name: Optional[str] = Field(None, title="Provided index name")
    uuid: Optional[str] = Field(None, title="Index UUID")

    # ILM / 기타 nested 설정
    lifecycle_name: Optional[str] = Field(None, title="ILM policy name (index.lifecycle.name)")

    analysis: Optional[Dict[str, Any]] = Field(None, title="Analysis settings (analyzers, filters, tokenizers...)")
    routing: Optional[Dict[str, Any]] = Field(None, title="Routing settings")

    # 그 외 index.* 설정 전체를 받고 싶을 때
    other_settings: Dict[str, Any] = Field(default_factory=dict, title="Other raw index.* settings")