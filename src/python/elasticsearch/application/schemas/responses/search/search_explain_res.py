from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Explain Summary
class ExplainScoreStepRes(BaseModel):
    key: str
    label: str
    value: Optional[float] = None
    formula_label: Optional[str] = None


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

# Explain Detail
class ExplainDetailNodeRes(BaseModel):
    key: str
    label: str
    value: Optional[float] = None
    description: Optional[str] = None
    children: List["ExplainDetailNodeRes"] = Field(default_factory=list)
    expandable: bool = False

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


class ExplainSectionRes(BaseModel):
    score: Optional[float] = None
    title: str
    items: List[ExplainDetailNodeRes] = Field(default_factory=list)


class QueryExplainScoreTimelineStepRes(BaseModel):
    key: str
    label: str
    value: Optional[float] = None
    description: Optional[str] = None


class QueryExplainMatchedTokenRes(BaseModel):
    token: str
    score: Optional[float] = None
    boost: Optional[float] = None
    idf: Optional[float] = None
    tf: Optional[float] = None


class QueryExplainFieldImpactRes(BaseModel):
    field: str
    source_value: Optional[Any] = None
    total_score: Optional[float] = None
    matched_tokens: List[QueryExplainMatchedTokenRes] = Field(default_factory=list)


class QueryExplainFilterMatchRes(BaseModel):
    label: str
    matched: bool = True
    description: Optional[str] = None


class QueryExplainScoringFunctionRes(BaseModel):
    label: str
    score: Optional[float] = None
    description: Optional[str] = None
    field: Optional[str] = None
    source_value: Optional[Any] = None


class SearchExplainDetailRes(BaseModel):
    index: str
    id: str
    doc_title: Optional[str] = None
    total_score: Optional[float] = None

    query_section: ExplainSectionRes
    rescore_sections: List[ExplainSectionRes] = Field(default_factory=list)
    term_factors: List[ExplainTermFactorRes] = Field(default_factory=list)

    score_timeline: List[QueryExplainScoreTimelineStepRes] = Field(default_factory=list)
    field_impacts: List[QueryExplainFieldImpactRes] = Field(default_factory=list)
    filter_matches: List[QueryExplainFilterMatchRes] = Field(default_factory=list)
    scoring_functions: List[QueryExplainScoringFunctionRes] = Field(default_factory=list)

    raw_explanation: Optional[Dict[str, Any]] = None
    source: Optional[Dict[str, Any]] = None


ExplainDetailNodeRes.model_rebuild()