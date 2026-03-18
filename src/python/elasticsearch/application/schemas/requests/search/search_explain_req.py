from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SearchExplainSummaryReq(BaseModel):
    index: str | List[str] = Field(..., description="검색 대상 인덱스")
    body: Dict[str, Any] = Field(..., description="표준 Elasticsearch search body")
    include_source_fields: bool = Field(
        default=False,
        description="응답에 source 포함 여부"
    )
    doc_title_fields: List[str] = Field(
        default_factory=lambda: ["GOODS_NM"],
        description="doc_title 생성에 사용할 source field 목록"
    )


class SearchExplainDetailReq(BaseModel):
    index: str | List[str] = Field(..., description="검색 대상 인덱스")
    body: Dict[str, Any] = Field(..., description="표준 Elasticsearch search body")
    doc_id: str = Field(..., description="상세를 조회할 문서 ID")
    include_raw_explain: bool = Field(default=False, description="원본 explain 포함 여부")
    include_source_fields: bool = Field(
        default=False,
        description="응답에 source 포함 여부"
    )
    doc_title_fields: List[str] = Field(
        default_factory=lambda: ["GOODS_NM"],
        description="doc_title 생성에 사용할 source field 목록"
    )