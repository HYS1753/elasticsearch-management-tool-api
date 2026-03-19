from typing import Any

from pydantic import BaseModel, Field


class DocumentHitItem(BaseModel):
    index: str = Field(alias="_index")
    id: str = Field(alias="_id")
    score: float | None = Field(default=None, alias="_score")
    source: dict[str, Any] = Field(default_factory=dict, alias="_source")
    sort: list[Any] | None = Field(default=None)

    model_config = {
        "populate_by_name": True,
    }


class DocumentSearchRes(BaseModel):
    took: int = Field(description="검색 소요 시간(ms)")
    timed_out: bool = Field(description="타임아웃 여부")
    total: int = Field(description="전체 문서 수")
    hits: list[DocumentHitItem] = Field(default_factory=list, description="문서 목록")