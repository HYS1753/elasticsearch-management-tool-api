from typing import Any

from pydantic import BaseModel, Field


class DocumentSearchReq(BaseModel):
    index_name: str = Field(description="조회 대상 인덱스명")
    query: dict[str, Any] | None = Field(default=None, description="Elasticsearch query DSL")
    from_: int = Field(default=0, ge=0, alias="from", description="검색 시작 offset")
    size: int = Field(default=20, ge=1, le=100, description="페이지 크기")
    sort: list[dict[str, str]] | None = Field(default=None, description="정렬 조건")

    model_config = {
        "populate_by_name": True,
    }