from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.python.elasticsearch.application.schemas.responses.search.search_explain_res import (
    ExplainScoreStepRes,
    ExplainSummaryHitRes, QueryExplainScoreTimelineStepRes, QueryExplainFieldImpactRes, QueryExplainFilterMatchRes,
    QueryExplainScoringFunctionRes, QueryExplainMatchedTokenRes,
)
from src.python.elasticsearch.application.schemas.responses.search.search_explain_res import (
    ExplainDetailNodeRes,
    ExplainSectionRes,
    ExplainTermFactorRes,
    SearchExplainDetailRes,
)

_SCORE_NORMALIZER_PREFIX = "score_normalizer_rescore"


# =========================================================
# Public API
# =========================================================

def summarize_hit(
    hit: Dict[str, Any],
    include_source_fields: bool = True,
    doc_title_fields: Optional[List[str]] = None
) -> ExplainSummaryHitRes:
    explanation = hit.get("_explanation") or {}
    score = hit.get("_score")
    source = hit.get("_source") or {}

    parsed = _parse_summary_from_explanation(explanation, final_score=score)

    doc_title = build_doc_title(
        source,
        doc_title_fields or [],
        hit.get("_id", "")
    )

    formula = _build_summary_formula(
        query_score=parsed["query_score"],
        rescore_steps=parsed["rescore_steps"],
        total_score=score,
    )

    return ExplainSummaryHitRes(
        index=hit.get("_index", ""),
        id=hit.get("_id", ""),
        doc_title=doc_title,
        total_score=score,
        query_score=parsed["query_score"],
        rescore_steps=parsed["rescore_steps"],
        formula=formula,
        source=source if include_source_fields else None,
    )


def build_doc_title(
    source: Dict[str, Any],
    doc_title_fields: List[str],
    doc_id: str
) -> str:
    if not doc_title_fields:
        return doc_id

    if not source:
        return doc_id

    parts: List[str] = []

    for field in doc_title_fields:
        value = source.get(field)

        if value is None:
            continue

        if isinstance(value, list):
            joined = ", ".join(
                str(v).strip() for v in value
                if v is not None and str(v).strip()
            )
            if joined:
                parts.append(joined)
        else:
            text = str(value).strip()
            if text:
                parts.append(text)

    if not parts:
        return doc_id

    dedup_parts = list(dict.fromkeys(parts))
    return " | ".join(dedup_parts)


def build_score_timeline(expl: Dict[str, Any], total_score: Optional[float]) -> List[QueryExplainScoreTimelineStepRes]:
    steps: List[QueryExplainScoreTimelineStepRes] = []

    original_query_score = _find_original_query_score(expl)
    if original_query_score is None and expl.get("value") is not None and _is_query_root(expl.get("description", "")):
        original_query_score = expl.get("value")

    if original_query_score is not None:
        steps.append(QueryExplainScoreTimelineStepRes(
            key="query",
            label="Original Query Score",
            value=original_query_score,
            description="검색어 매칭으로 계산된 원본 점수"
        ))

    # custom score normalizer
    custom_nodes = _find_all_nodes_by_prefix(expl, _SCORE_NORMALIZER_PREFIX)
    for idx, node in enumerate(custom_nodes, start=1):
        steps.append(QueryExplainScoreTimelineStepRes(
            key=f"rescore_normalizer_{idx}",
            label=f"Rescore {idx} - Score Normalizer",
            value=_find_factor_applied_score(node) or node.get("value"),
            description=_find_normalizer_type(node) or "score_normalizer"
        ))

    # function score / field value factor
    function_nodes = _find_all_nodes_contains(expl, "function score")
    for idx, node in enumerate(function_nodes, start=1):
        steps.append(QueryExplainScoreTimelineStepRes(
            key=f"function_score_{idx}",
            label=f"Function Score {idx}",
            value=node.get("value"),
            description=node.get("description")
        ))

    if total_score is not None:
        steps.append(QueryExplainScoreTimelineStepRes(
            key="total",
            label="Total Score",
            value=total_score,
            description="최종 점수"
        ))

    return steps


def build_field_impacts(
    expl: Dict[str, Any],
    source: Dict[str, Any]
) -> List[QueryExplainFieldImpactRes]:
    term_factors = _extract_term_factors(expl)
    grouped: Dict[str, QueryExplainFieldImpactRes] = {}

    for factor in term_factors:
        field_name = factor.field or "unknown"

        if field_name not in grouped:
            grouped[field_name] = QueryExplainFieldImpactRes(
                field=field_name,
                source_value=source.get(field_name),
                total_score=0.0,
                matched_tokens=[]
            )

        grouped[field_name].matched_tokens.append(
            QueryExplainMatchedTokenRes(
                token=factor.term or "unknown",
                score=factor.score,
                boost=factor.boost,
                idf=factor.idf,
                tf=factor.tf
            )
        )

        grouped[field_name].total_score = (grouped[field_name].total_score or 0.0) + (factor.score or 0.0)

    return sorted(grouped.values(), key=lambda x: x.total_score or 0.0, reverse=True)


def build_filter_matches(request_body: Dict[str, Any], source: Dict[str, Any]) -> List[QueryExplainFilterMatchRes]:
    results: List[QueryExplainFilterMatchRes] = []

    query = request_body.get("query", {})
    bool_query = query.get("bool", {})
    filters = bool_query.get("filter", [])

    for f in filters:
        if "term" in f:
            field, value_obj = next(iter(f["term"].items()))
            value = value_obj.get("value") if isinstance(value_obj, dict) else value_obj
            results.append(QueryExplainFilterMatchRes(
                label=f"{field} = {value}",
                matched=True,
                description=f"source value: {source.get(field)}"
            ))

        elif "range" in f:
            field, range_obj = next(iter(f["range"].items()))
            results.append(QueryExplainFilterMatchRes(
                label=f"{field} range",
                matched=True,
                description=str(range_obj)
            ))

        else:
            results.append(QueryExplainFilterMatchRes(
                label="filter condition",
                matched=True,
                description=str(f)
            ))

    return results


def build_scoring_functions(
    expl: Dict[str, Any],
    source: Dict[str, Any]
) -> List[QueryExplainScoringFunctionRes]:
    results: List[QueryExplainScoringFunctionRes] = []

    field_value_nodes = _find_all_nodes_contains(expl, "field value function:")
    for node in field_value_nodes:
        desc = node.get("description", "") or ""
        field_name = _extract_field_name_from_field_value_function(desc)

        results.append(QueryExplainScoringFunctionRes(
            label="Field Value Function",
            score=node.get("value"),
            description=desc,
            field=field_name,
            source_value=source.get(field_name) if field_name else None
        ))

    function_score_nodes = _find_all_nodes_contains(expl, "function score")
    for node in function_score_nodes:
        results.append(QueryExplainScoringFunctionRes(
            label="Function Score",
            score=node.get("value"),
            description=node.get("description")
        ))

    return results


def build_detail(
    hit: Dict[str, Any],
    request_body: Dict[str, Any],
    doc_title_fields: List[str],
    include_source_fields: bool = True,
    include_raw_explain: bool = False
) -> SearchExplainDetailRes:
    explanation = hit.get("_explanation") or {}
    source = hit.get("_source") or {}

    doc_title = build_doc_title(
        source,
        doc_title_fields or [],
        hit.get("_id", "")
    )

    detail_parsed = _parse_detail_from_explanation(
        explanation,
        final_score=hit.get("_score")
    )

    query_section = detail_parsed["query_section"]
    rescore_sections = detail_parsed["rescore_sections"]

    query_explanation = _extract_query_explanation_tree(explanation)

    term_factors = _extract_term_factors(query_explanation) if query_explanation else []
    score_timeline = build_score_timeline(explanation, hit.get("_score"))
    field_impacts = build_field_impacts(query_explanation, source) if query_explanation else []
    filter_matches = build_filter_matches(request_body, source)
    scoring_functions = build_scoring_functions(query_explanation, source) if query_explanation else []

    return SearchExplainDetailRes(
        index=hit.get("_index", ""),
        id=hit.get("_id", ""),
        doc_title=doc_title,
        total_score=hit.get("_score"),
        query_section=query_section,
        rescore_sections=rescore_sections,
        term_factors=term_factors,
        score_timeline=score_timeline,
        field_impacts=field_impacts,
        filter_matches=filter_matches,
        scoring_functions=scoring_functions,
        raw_explanation=explanation if include_raw_explain else None,
        source=source if include_source_fields else None
    )


# =========================================================
# Summary parsing
# =========================================================

def _parse_summary_from_explanation(
    expl: Dict[str, Any],
    final_score: Optional[float] = None
) -> Dict[str, Any]:
    """
    explain tree를 보고 summary용
    - query_score
    - rescore_steps
    를 안정적으로 추출한다.
    """
    if not expl:
        return {
            "query_score": final_score,
            "rescore_steps": []
        }

    desc = expl.get("description", "") or ""

    # Case 1) query only
    if _is_query_root(desc):
        return {
            "query_score": expl.get("value"),
            "rescore_steps": []
        }

    # Case 2) single custom rescore root
    if desc.startswith(_SCORE_NORMALIZER_PREFIX):
        return _parse_single_custom_rescore_summary(expl)

    # Case 3) multi-step rescore root (e.g. "sum of:")
    if desc.startswith("sum of:"):
        return _parse_sum_root_summary(expl, final_score)

    # fallback
    query_score = _find_original_query_score(expl)
    if query_score is not None:
        return {
            "query_score": query_score,
            "rescore_steps": []
        }

    return {
        "query_score": expl.get("value"),
        "rescore_steps": []
    }


def _parse_single_custom_rescore_summary(expl: Dict[str, Any]) -> Dict[str, Any]:
    query_score = _find_original_query_score(expl)
    normalizer_type = _find_normalizer_type(expl)
    normalized_score = _find_normalized_score(expl)
    factor_applied_score = _find_factor_applied_score(expl)
    factor_mode = _find_factor_mode(expl)

    rescore_steps: List[ExplainScoreStepRes] = []

    if normalized_score is not None:
        rescore_steps.append(
            ExplainScoreStepRes(
                key="score_normalizer_normalized",
                label=f"score_normalizer:{normalizer_type or 'unknown'}",
                value=normalized_score,
                formula_label=f"normalize({normalizer_type or 'unknown'})"
            )
        )

    if factor_applied_score is not None:
        rescore_steps.append(
            ExplainScoreStepRes(
                key="score_normalizer_factor_applied",
                label=f"score_normalizer_factor:{factor_mode or 'unknown'}",
                value=factor_applied_score,
                formula_label=f"factor({factor_mode or 'unknown'})"
            )
        )

    return {
        "query_score": query_score,
        "rescore_steps": rescore_steps
    }


def _parse_sum_root_summary(
    expl: Dict[str, Any],
    final_score: Optional[float] = None
) -> Dict[str, Any]:
    """
    root = "sum of:" 인 경우
    detail마다 rescore step일 가능성이 높다.
    예:
    - custom score_normalizer (product of -> score_normalizer_rescore ...)
    - query rescore/function_score (product of -> function score ...)
    """
    details = expl.get("details", []) or []

    query_score = _find_original_query_score(expl)
    rescore_steps: List[ExplainScoreStepRes] = []

    for idx, d in enumerate(details, start=1):
        step = _parse_rescore_step_node(d, idx)
        if step is not None:
            rescore_steps.append(step)

    # query_score를 못 찾았으면 fallback으로 root 내부에서 찾기
    if query_score is None:
        query_score = _find_original_query_score(expl)

    return {
        "query_score": query_score,
        "rescore_steps": rescore_steps
    }


def _parse_rescore_step_node(node: Dict[str, Any], idx: int) -> Optional[ExplainScoreStepRes]:
    """
    sum of: 하위 각 node를 보고 rescore step 1개로 요약한다.
    """
    custom_node = _find_first_node_by_prefix(node, _SCORE_NORMALIZER_PREFIX)
    if custom_node is not None:
        normalizer_type = _find_normalizer_type(custom_node)
        factor_applied_score = _find_factor_applied_score(custom_node)
        normalized_score = _find_normalized_score(custom_node)
        factor_mode = _find_factor_mode(custom_node)

        # summary에서는 실제 step 결과값이 더 중요하므로 factor_applied_score 우선
        step_value = factor_applied_score if factor_applied_score is not None else normalized_score

        return ExplainScoreStepRes(
            key=f"rescore_{idx}_score_normalizer",
            label=f"score_normalizer:{normalizer_type or 'unknown'}",
            value=step_value,
            formula_label=f"rescore{idx}:{normalizer_type or 'score_normalizer'}"
        )

    function_score_node = _find_first_node_contains(node, "function score")
    if function_score_node is not None:
        return ExplainScoreStepRes(
            key=f"rescore_{idx}_function_score",
            label="query_rescore:function_score",
            value=node.get("value"),
            formula_label=f"rescore{idx}:function_score"
        )

    field_value_node = _find_first_node_contains(node, "field value function:")
    if field_value_node is not None:
        return ExplainScoreStepRes(
            key=f"rescore_{idx}_field_value_factor",
            label="query_rescore:field_value_factor",
            value=node.get("value"),
            formula_label=f"rescore{idx}:field_value_factor"
        )

    # generic fallback
    desc = node.get("description", "") or ""
    val = node.get("value")
    if val is not None and desc:
        return ExplainScoreStepRes(
            key=f"rescore_{idx}_generic",
            label=f"rescore:{desc}",
            value=val,
            formula_label=f"rescore{idx}"
        )

    return None


def _build_summary_formula(
    query_score: Optional[float],
    rescore_steps: List[ExplainScoreStepRes],
    total_score: Optional[float]
) -> str:
    """
    formula를 실제 점수 변화 흐름 기준으로 표현한다.

    예)
    - query only
      query(8.5613) = total(8.5613)

    - single rescore
      query(8.5613) -> rescore1:min_max(1.0000) = total(1.0000)

    - multi rescore
      query(7.8666) -> rescore1:min_max(0.6122), 0.6122 + rescore2:function_score(64.0000) = total(64.6122)
    """
    if query_score is None and not rescore_steps:
        return f"total({float(total_score):.4f})" if total_score is not None else "total(null)"

    # query only
    if query_score is not None and not rescore_steps:
        if total_score is not None:
            return f"query({query_score:.4f}) = total({float(total_score):.4f})"
        return f"query({query_score:.4f})"

    valid_steps = [step for step in rescore_steps if step.value is not None]

    if query_score is None and valid_steps:
        if len(valid_steps) == 1:
            step = valid_steps[0]
            label = step.formula_label or step.label or "rescore1"
            if total_score is not None:
                return f"{label}({step.value:.4f}) = total({float(total_score):.4f})"
            return f"{label}({step.value:.4f})"

        expr_parts: List[str] = []
        current_value = valid_steps[0].value
        first_label = valid_steps[0].formula_label or valid_steps[0].label or "rescore1"
        expr_parts.append(f"{first_label}({current_value:.4f})")

        for step in valid_steps[1:]:
            label = step.formula_label or step.label or "rescore"
            expr_parts.append(f"{current_value:.4f} + {label}({step.value:.4f})")
            current_value = current_value + step.value

        if total_score is not None:
            return ", ".join(expr_parts) + f" = total({float(total_score):.4f})"
        return ", ".join(expr_parts)

    # query + rescore
    first_step = valid_steps[0] if valid_steps else None

    if first_step is None:
        if total_score is not None:
            return f"query({query_score:.4f}) = total({float(total_score):.4f})"
        return f"query({query_score:.4f})"

    first_label = first_step.formula_label or first_step.label or "rescore1"
    expressions: List[str] = [f"query({query_score:.4f}) -> {first_label}({first_step.value:.4f})"]

    current_value = first_step.value

    for step in valid_steps[1:]:
        label = step.formula_label or step.label or "rescore"
        expressions.append(f"{current_value:.4f} + {label}({step.value:.4f})")
        current_value = current_value + step.value

    if total_score is not None:
        return " | ".join(expressions) + f" = total({float(total_score):.4f})"

    return " | ".join(expressions)


# =========================================================
# Detail parsing
# =========================================================

def _parse_detail_from_explanation(
    expl: Dict[str, Any],
    final_score: Optional[float] = None
) -> Dict[str, Any]:
    if not expl:
        return {
            "query_section": ExplainSectionRes(title="Query Score", score=final_score, items=[]),
            "rescore_sections": [],
            "term_factors": []
        }

    desc = expl.get("description", "") or ""

    # query only
    if _is_query_root(desc):
        return {
            "query_section": ExplainSectionRes(
                title="Query Score",
                score=expl.get("value"),
                items=[_to_detail_node(expl)]
            ),
            "rescore_sections": [],
            "term_factors": _extract_term_factors(expl)
        }

    # single custom rescore root
    if desc.startswith(_SCORE_NORMALIZER_PREFIX):
        query_section, rescore_sections = _build_custom_rescore_detail(expl)
        return {
            "query_section": query_section,
            "rescore_sections": rescore_sections,
            "term_factors": _extract_term_factors(expl)
        }

    # multi rescore root
    if desc.startswith("sum of:"):
        return _build_sum_root_detail(expl, final_score)

    # fallback
    return {
        "query_section": ExplainSectionRes(
            title="Query Score",
            score=expl.get("value"),
            items=[_to_detail_node(expl)]
        ),
        "rescore_sections": [],
        "term_factors": _extract_term_factors(expl)
    }


def _build_sum_root_detail(
    explanation: Dict[str, Any],
    final_score: Optional[float] = None
) -> Dict[str, Any]:
    details = explanation.get("details", []) or []

    query_items: List[ExplainDetailNodeRes] = []
    query_score = _find_original_query_score(explanation)
    rescore_sections: List[ExplainSectionRes] = []

    # query 원점수는 custom normalizer 내부 original query score에서 꺼내고
    # rescore sections는 sum의 각 child마다 하나씩 만든다.
    original_query_node = _find_first_node_by_exact_description(explanation, "original query score")
    if original_query_node is not None:
        query_items.append(_to_detail_node(original_query_node))

    for idx, d in enumerate(details, start=1):
        section = _build_rescore_section_from_sum_child(d, idx)
        if section is not None:
            rescore_sections.append(section)

    return {
        "query_section": ExplainSectionRes(
            title="Query Score",
            score=query_score if query_score is not None else final_score,
            items=query_items
        ),
        "rescore_sections": rescore_sections,
        "term_factors": _extract_term_factors(explanation)
    }


def _build_rescore_section_from_sum_child(
    node: Dict[str, Any],
    idx: int
) -> Optional[ExplainSectionRes]:
    custom_node = _find_first_node_by_prefix(node, _SCORE_NORMALIZER_PREFIX)
    if custom_node is not None:
        normalizer_type = _find_normalizer_type(custom_node)
        return ExplainSectionRes(
            title=f"Rescore {idx} - Score Normalizer ({normalizer_type or 'unknown'})",
            score=node.get("value"),
            items=[_to_detail_node(node)]
        )

    function_score_node = _find_first_node_contains(node, "function score")
    if function_score_node is not None:
        return ExplainSectionRes(
            title=f"Rescore {idx} - Function Score",
            score=node.get("value"),
            items=[_to_detail_node(node)]
        )

    return ExplainSectionRes(
        title=f"Rescore {idx}",
        score=node.get("value"),
        items=[_to_detail_node(node)]
    )


def _build_custom_rescore_detail(
    explanation: Dict[str, Any]
) -> tuple[ExplainSectionRes, List[ExplainSectionRes]]:
    details = explanation.get("details", []) or []

    query_items: List[ExplainDetailNodeRes] = []
    rescore_sections: List[ExplainSectionRes] = []
    query_score = None

    normalized_node = None
    factor_applied_node = None

    for d in details:
        desc = d.get("description", "") or ""
        val = d.get("value")

        if desc == "score_normalizer_rescore.original_query_score" or desc == "original query score":
            query_score = val
            query_items.append(_to_detail_node(d))

        elif desc.startswith("score_normalizer_rescore.normalized_score[type=") or desc.startswith("normalized score using ") or desc.startswith("normalized score by "):
            normalized_node = d

        elif desc.startswith("score_normalizer_rescore.factor_applied_score") or desc == "score after factor application":
            factor_applied_node = d

    if normalized_node is not None:
        normalizer_type = _find_normalizer_type(normalized_node) or _find_normalizer_type(explanation)
        rescore_sections.append(
            ExplainSectionRes(
                title=f"Rescore - Score Normalizer ({normalizer_type or 'unknown'})",
                score=normalized_node.get("value"),
                items=[_to_detail_node(normalized_node)]
            )
        )

    if factor_applied_node is not None:
        factor_mode = _find_factor_mode(factor_applied_node) or _find_factor_mode(explanation)
        rescore_sections.append(
            ExplainSectionRes(
                title=f"Rescore - Factor Applied ({factor_mode or 'unknown'})",
                score=factor_applied_node.get("value"),
                items=[_to_detail_node(factor_applied_node)]
            )
        )

    return (
        ExplainSectionRes(title="Query Score", score=query_score, items=query_items),
        rescore_sections
    )


# =========================================================
# Detail helpers
# =========================================================

def _to_detail_node(expl: Dict[str, Any]) -> ExplainDetailNodeRes:
    children = [_to_detail_node(d) for d in (expl.get("details", []) or [])]
    return ExplainDetailNodeRes(
        key=(expl.get("description", "") or "")[:120],
        label=_to_ui_label(expl.get("description", "")),
        value=expl.get("value"),
        description=expl.get("description"),
        children=children,
        expandable=len(children) > 0
    )


def _to_ui_label(description: str) -> str:
    desc = description or ""

    if desc.startswith("sum of:"):
        return "Sum"
    if desc.startswith("product of:"):
        return "Product"
    if desc.startswith("weight("):
        return "BM25 Weight"
    if desc.startswith("score(freq="):
        return "BM25 Score"
    if desc == "boost":
        return "Boost"
    if desc.startswith("idf,"):
        return "IDF"
    if desc.startswith("tf,"):
        return "TF"
    if desc.startswith("field value function:"):
        return "Field Value Function"
    if desc == "primaryWeight":
        return "Primary Weight"
    if desc == "secondaryWeight":
        return "Secondary Weight"
    if desc == "*:*":
        return "Match All"
    if desc.startswith("score_normalizer_rescore.original_query_score") or desc == "original query score":
        return "Original Query Score"
    if desc.startswith("score_normalizer_rescore.normalized_score") or desc.startswith("normalized score using ") or desc.startswith("normalized score by "):
        return "Normalized Score"
    if desc.startswith("score_normalizer_rescore.factor_applied_score") or desc == "score after factor application":
        return "Factor Applied Score"
    if desc.startswith("score_normalizer_rescore.factor_input_score") or desc == "score before factor application":
        return "Factor Input Score"
    if desc.startswith("score_normalizer_rescore.factor_mode") or desc.startswith("factor mode ["):
        return "Factor Mode"
    if desc.startswith("score_normalizer_rescore.factor") or desc == "factor":
        return "Factor"
    return desc


def _extract_term_factors(expl: Dict[str, Any]) -> List[ExplainTermFactorRes]:
    results: List[ExplainTermFactorRes] = []

    def walk(node: Dict[str, Any]):
        desc = node.get("description", "") or ""
        m = re.match(r"weight\(([^:]+):(.+?) in \d+\)", desc)
        if m:
            field = m.group(1)
            term = m.group(2)
            score = node.get("value")

            factor = ExplainTermFactorRes(field=field, term=term, score=score)

            def walk_term(n: Dict[str, Any]):
                nd = (n.get("description", "") or "").lower()
                if nd == "boost":
                    factor.boost = n.get("value")
                elif nd.startswith("idf,"):
                    factor.idf = n.get("value")
                elif nd.startswith("tf,"):
                    factor.tf = n.get("value")
                elif nd.startswith("freq,"):
                    factor.freq = n.get("value")
                elif nd.startswith("dl,"):
                    factor.dl = n.get("value")
                elif nd.startswith("avgdl,"):
                    factor.avgdl = n.get("value")
                for c in n.get("details", []) or []:
                    walk_term(c)

            walk_term(node)
            results.append(factor)

        for child in node.get("details", []) or []:
            walk(child)

    walk(expl)
    return results


# =========================================================
# Tree search helpers
# =========================================================

def _is_query_root(description: str) -> bool:
    if not description:
        return False
    return (
        description.startswith("weight(")
        or description.startswith("score(")
    )


def _find_original_query_score(node: Dict[str, Any]) -> Optional[float]:
    target = _find_first_node_by_exact_description(node, "original query score")
    if target is not None:
        return target.get("value")
    return None


def _find_normalized_score(node: Dict[str, Any]) -> Optional[float]:
    target = _find_first_node_by_prefixes(
        node,
        [
            "score_normalizer_rescore.normalized_score[type=",
            "normalized score using ",
            "normalized score by ",
        ]
    )
    return target.get("value") if target is not None else None


def _find_factor_applied_score(node: Dict[str, Any]) -> Optional[float]:
    target = _find_first_node_by_prefixes(
        node,
        [
            "score_normalizer_rescore.factor_applied_score",
            "score after factor application",
            "final rescored score",
        ]
    )
    return target.get("value") if target is not None else None


def _find_factor_mode(node: Dict[str, Any]) -> Optional[str]:
    target = _find_first_node_by_prefixes(
        node,
        [
            "score_normalizer_rescore.factor_mode[",
            "factor mode [",
            "factor mode = ",
        ]
    )
    if target is None:
        return None

    desc = target.get("description", "") or ""

    m = re.search(r"factor_mode\[([a-zA-Z0-9_\-]+)\]", desc)
    if m:
        return m.group(1)

    m = re.search(r"factor mode \[([a-zA-Z0-9_\-]+)\]", desc)
    if m:
        return m.group(1)

    if desc.startswith("factor mode = "):
        return desc.replace("factor mode = ", "").strip()

    return None


def _find_normalizer_type(node: Dict[str, Any]) -> Optional[str]:
    # 1) custom prefix type
    target = _find_first_node_by_prefix(node, _SCORE_NORMALIZER_PREFIX)
    if target is not None:
        desc = target.get("description", "") or ""
        m = re.search(r"type=([a-zA-Z0-9_\-]+)", desc)
        if m:
            return m.group(1)

    # 2) normalized score using xxx
    target = _find_first_node_by_prefixes(
        node,
        [
            "score_normalizer_rescore.normalized_score[type=",
            "normalized score using ",
            "normalized score by ",
        ]
    )
    if target is not None:
        desc = target.get("description", "") or ""
        m = re.search(r"type=([a-zA-Z0-9_\-]+)", desc)
        if m:
            return m.group(1)
        if desc.startswith("normalized score using "):
            return desc.replace("normalized score using ", "").strip()
        if desc.startswith("normalized score by "):
            return desc.replace("normalized score by ", "").strip()

    return None


def _find_first_node_by_exact_description(node: Dict[str, Any], description: str) -> Optional[Dict[str, Any]]:
    if (node.get("description", "") or "") == description:
        return node

    for child in node.get("details", []) or []:
        found = _find_first_node_by_exact_description(child, description)
        if found is not None:
            return found
    return None


def _find_first_node_by_prefix(node: Dict[str, Any], prefix: str) -> Optional[Dict[str, Any]]:
    desc = node.get("description", "") or ""
    if desc.startswith(prefix):
        return node

    for child in node.get("details", []) or []:
        found = _find_first_node_by_prefix(child, prefix)
        if found is not None:
            return found
    return None


def _find_first_node_contains(node: Dict[str, Any], text: str) -> Optional[Dict[str, Any]]:
    desc = node.get("description", "") or ""
    if text in desc:
        return node

    for child in node.get("details", []) or []:
        found = _find_first_node_contains(child, text)
        if found is not None:
            return found
    return None


def _find_first_node_by_prefixes(
    node: Dict[str, Any],
    prefixes: List[str]
) -> Optional[Dict[str, Any]]:
    desc = node.get("description", "") or ""
    for prefix in prefixes:
        if desc.startswith(prefix):
            return node

    for child in node.get("details", []) or []:
        found = _find_first_node_by_prefixes(child, prefixes)
        if found is not None:
            return found

    return None

def _extract_field_name_from_field_value_function(desc: str) -> Optional[str]:
    m = re.search(r"doc\['([^']+)'\]", desc)
    return m.group(1) if m else None

def _find_all_nodes_by_prefix(node: Dict[str, Any], prefix: str) -> List[Dict[str, Any]]:
    results = []
    desc = node.get("description", "") or ""
    if desc.startswith(prefix):
        results.append(node)

    for child in node.get("details", []) or []:
        results.extend(_find_all_nodes_by_prefix(child, prefix))
    return results


def _find_all_nodes_contains(node: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
    results = []
    desc = node.get("description", "") or ""
    if text in desc:
        results.append(node)

    for child in node.get("details", []) or []:
        results.extend(_find_all_nodes_contains(child, text))
    return results

def _extract_query_explanation_tree(expl: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    explain 전체 트리에서 '원본 query 점수 계산 영역'만 추출한다.

    우선순위:
    1. custom rescorer 내부의 'original query score' 하위
    2. query only explain이면 root 자체
    3. 못 찾으면 None
    """
    if not expl:
        return None

    desc = expl.get("description", "") or ""

    # query only
    if _is_query_root(desc):
        return expl

    # custom rescore 내부 original query score
    original_query_node = _find_first_node_by_exact_description(expl, "original query score")
    if original_query_node:
        details = original_query_node.get("details", []) or []
        if details:
            return details[0]
        return original_query_node

    return None