from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# =========================
# Summary
# =========================

class ExplainScoreStepRes(BaseModel):
    key: str
    label: str
    value: Optional[float] = None
    formula_label: Optional[str] = None
    operator: Optional[str] = None
    operator_value: Optional[float] = None


class ExplainSummaryHitRes(BaseModel):
    index: str
    id: str
    doc_title: Optional[str] = None
    total_score: Optional[float] = None
    query_score: Optional[float] = None
    rescore_steps: List[ExplainScoreStepRes] = Field(default_factory=list)
    formula: str = ""
    source: Optional[Dict[str, Any]] = None


class SearchExplainSummaryRes(BaseModel):
    took: int
    timed_out: bool
    total_hits: Optional[int] = None
    hits: List[ExplainSummaryHitRes] = Field(default_factory=list)


# =========================
# Shared / Detail
# =========================

class ExplainTermFactorRes(BaseModel):
    field: Optional[str] = None
    term: Optional[str] = None
    score: Optional[float] = None
    boost: Optional[float] = None
    idf: Optional[float] = None
    tf: Optional[float] = None
    freq: Optional[float] = None
    dl: Optional[float] = None
    avgdl: Optional[float] = None
    n_val: Optional[float] = None
    N_val: Optional[float] = None
    k1: Optional[float] = None
    b: Optional[float] = None


class ExplainMatchedTokenRes(BaseModel):
    token: str
    score: Optional[float] = None
    boost: Optional[float] = None
    idf: Optional[float] = None
    tf: Optional[float] = None
    freq: Optional[float] = None
    dl: Optional[float] = None
    avgdl: Optional[float] = None
    n_val: Optional[float] = None
    N_val: Optional[float] = None
    k1: Optional[float] = None
    b: Optional[float] = None
    description: Optional[str] = None


class ExplainFieldScoreGroupRes(BaseModel):
    field: str
    source_value: Optional[Any] = None
    total_score: Optional[float] = None
    matched_tokens: List[ExplainMatchedTokenRes] = Field(default_factory=list)


class ExplainFilterRes(BaseModel):
    label: str
    matched: bool = True
    source_value: Optional[Any] = None
    description: Optional[str] = None


class ExplainFunctionScoreRes(BaseModel):
    label: str
    score: Optional[float] = None
    field: Optional[str] = None
    source_value: Optional[Any] = None
    description: Optional[str] = None

    operation: Optional[str] = None          # sum / multiply / score_mode / boost_mode
    filter_label: Optional[str] = None       # 어떤 filter에 의해 적용됐는지
    matched: Optional[bool] = None           # filter 매칭 여부
    params: Optional[Dict[str, Any]] = None  # weight, factor, modifier, gauss params 등


class ExplainRescoreDetailRes(BaseModel):
    order: int
    type: str
    title: str
    score: Optional[float] = None
    description: Optional[str] = None
    details: List[ExplainFunctionScoreRes] = Field(default_factory=list)

    score_mode: Optional[str] = None
    boost_mode: Optional[str] = None
    query_weight: Optional[float] = None
    rescore_query_weight: Optional[float] = None
    rescore_query_score: Optional[float] = None
    rescore_query_structure: Optional["QueryStructureNode"] = None



class QueryStructureNode(BaseModel):
    type: str = Field(description="sum_of | max_of | min_of | mean_of | product_of | knn | bm25 | function_score | constant_score | weight | unknown")
    description: str
    value: float
    field: Optional[str] = None
    term: Optional[str] = None
    tie_breaker: Optional[float] = None
    details: List["QueryStructureNode"] = Field(default_factory=list)


class ExplainQueryDetailRes(BaseModel):
    original_score: Optional[float] = None
    filters: List[ExplainFilterRes] = Field(default_factory=list)
    bm25_groups: List[ExplainFieldScoreGroupRes] = Field(default_factory=list)
    function_scores: List[ExplainFunctionScoreRes] = Field(default_factory=list)

    function_score_mode: Optional[str] = None
    function_boost_mode: Optional[str] = None
    function_score_combined: Optional[float] = None   # functions끼리 합쳐진 점수
    final_query_score: Optional[float] = None         # boost_mode 적용 후 최종 query score
    query_structure: Optional[QueryStructureNode] = None



class ScoreSubDetail(BaseModel):
    field: Optional[str] = None
    score: Optional[float] = None
    tokens: List[str] = Field(default_factory=list)
    clause_type: Optional[str] = None  # "must", "should", "filter", "knn"
    description: Optional[str] = None


class QueryExplainScoreTimelineStepRes(BaseModel):
    key: str
    label: str
    value: Optional[float] = None
    description: Optional[str] = None
    formula_label: Optional[str] = None
    operator: Optional[str] = None
    operator_value: Optional[float] = None
    sub_details: List[ScoreSubDetail] = Field(default_factory=list)


class SearchExplainDetailRes(BaseModel):
    index: str
    id: str
    doc_title: Optional[str] = None
    total_score: Optional[float] = None
    query: ExplainQueryDetailRes
    rescores: List[ExplainRescoreDetailRes] = Field(default_factory=list)
    score_timeline: List[QueryExplainScoreTimelineStepRes] = Field(default_factory=list)
    raw_explanation: Optional[Dict[str, Any]] = None
    source: Optional[Dict[str, Any]] = None


QueryStructureNode.model_rebuild()