from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.python.elasticsearch.application.schemas.responses.search.search_explain_res import (
    ExplainSummaryHitRes,
    ExplainScoreStepRes,
    SearchExplainDetailRes,
    ExplainQueryDetailRes,
    ExplainFieldScoreGroupRes,
    ExplainMatchedTokenRes,
    ExplainFilterRes,
    ExplainFunctionScoreRes,
    ExplainRescoreDetailRes,
    ExplainTermFactorRes,
    QueryExplainScoreTimelineStepRes,
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

    query_expl = _extract_query_explanation_tree(explanation)
    rescore_nodes = _extract_rescore_nodes(explanation)

    query_detail = build_query_detail(
        query_expl=query_expl,
        request_body=request_body,
        source=source,
        fallback_score=_find_original_query_score(explanation)
    )

    rescores = build_rescore_details(
        rescore_nodes=rescore_nodes,
        request_body=request_body,
        source=source
    )

    score_timeline = build_score_timeline(explanation, hit.get("_score"))

    return SearchExplainDetailRes(
        index=hit.get("_index", ""),
        id=hit.get("_id", ""),
        doc_title=doc_title,
        total_score=hit.get("_score"),
        query=query_detail,
        rescores=rescores,
        score_timeline=score_timeline,
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
    if not expl:
        return {
            "query_score": final_score,
            "rescore_steps": []
        }

    desc = expl.get("description", "") or ""

    if _is_query_root(desc):
        return {
            "query_score": expl.get("value"),
            "rescore_steps": []
        }

    if desc.startswith(_SCORE_NORMALIZER_PREFIX):
        return _parse_single_custom_rescore_summary(expl)

    if desc.startswith("sum of:"):
        return _parse_sum_root_summary(expl, final_score)

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
    details = expl.get("details", []) or []

    query_score = _find_original_query_score(expl)
    rescore_steps: List[ExplainScoreStepRes] = []

    for idx, d in enumerate(details, start=1):
        step = _parse_rescore_step_node(d, idx)
        if step is not None:
            rescore_steps.append(step)

    if query_score is None:
        query_score = _find_original_query_score(expl)

    return {
        "query_score": query_score,
        "rescore_steps": rescore_steps
    }


def _parse_rescore_step_node(node: Dict[str, Any], idx: int) -> Optional[ExplainScoreStepRes]:
    custom_node = _find_first_node_by_prefix(node, _SCORE_NORMALIZER_PREFIX)
    if custom_node is not None:
        normalizer_type = _find_normalizer_type(custom_node)
        factor_applied_score = _find_factor_applied_score(custom_node)
        normalized_score = _find_normalized_score(custom_node)

        step_value = factor_applied_score if factor_applied_score is not None else normalized_score

        return ExplainScoreStepRes(
            key=f"rescore_{idx}_score_normalizer",
            label=f"score_normalizer:{normalizer_type or 'unknown'}",
            value=step_value,
            formula_label=f"rescore{idx}:{normalizer_type or 'score_normalizer'}"
        )

    field_value_node = _find_first_node_contains(node, "field value function:")
    if field_value_node is not None:
        return ExplainScoreStepRes(
            key=f"rescore_{idx}_field_value_factor",
            label="query_rescore:field_value_factor",
            value=node.get("value"),
            formula_label=f"rescore{idx}:field_value_factor"
        )

    function_score_node = _find_first_node_contains(node, "function score")
    if function_score_node is not None:
        return ExplainScoreStepRes(
            key=f"rescore_{idx}_function_score",
            label="query_rescore:function_score",
            value=node.get("value"),
            formula_label=f"rescore{idx}:function_score"
        )

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
    if query_score is None and not rescore_steps:
        return f"total({float(total_score):.4f})" if total_score is not None else "total(null)"

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
            return " | ".join(expr_parts) + f" = total({float(total_score):.4f})"
        return " | ".join(expr_parts)

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

    rescore_nodes = _extract_rescore_nodes(expl)

    for idx, node in enumerate(rescore_nodes, start=1):
        custom_node = _find_first_node_by_prefix(node, _SCORE_NORMALIZER_PREFIX)
        if custom_node is not None:
            steps.append(QueryExplainScoreTimelineStepRes(
                key=f"rescore_{idx}_normalizer",
                label=f"Rescore {idx}",
                value=_find_factor_applied_score(custom_node) or node.get("value"),
                description=f"score_normalizer:{_find_normalizer_type(custom_node) or 'unknown'}"
            ))
            continue

        field_value_nodes = _find_all_nodes_contains(node, "field value function:")
        if field_value_nodes:
            steps.append(QueryExplainScoreTimelineStepRes(
                key=f"rescore_{idx}_function_score",
                label=f"Rescore {idx}",
                value=node.get("value"),
                description="function_score / field_value_factor"
            ))
            continue

        steps.append(QueryExplainScoreTimelineStepRes(
            key=f"rescore_{idx}",
            label=f"Rescore {idx}",
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


def build_query_detail(
    query_expl: Optional[Dict[str, Any]],
    request_body: Dict[str, Any],
    source: Dict[str, Any],
    fallback_score: Optional[float] = None
) -> ExplainQueryDetailRes:
    query_fs_meta = _extract_query_function_score_meta(request_body)

    if not query_expl:
        return ExplainQueryDetailRes(
            original_score=fallback_score,
            filters=build_filter_matches(request_body, source),
            bm25_groups=[],
            function_scores=[],
            function_score_mode=query_fs_meta.get("score_mode"),
            function_boost_mode=query_fs_meta.get("boost_mode"),
            function_score_combined=None,
            final_query_score=fallback_score,
        )

    term_factors = _extract_term_factors(query_expl)
    function_scores = build_query_function_scores(
        query_expl=query_expl,
        request_body=request_body,
        source=source
    )

    function_score_combined = _find_query_function_combined_score(query_expl)
    final_query_score = query_expl.get("value") if query_expl.get("value") is not None else fallback_score

    return ExplainQueryDetailRes(
        original_score=_find_original_text_query_score(query_expl) or final_query_score,
        filters=build_filter_matches(request_body, source),
        bm25_groups=build_field_score_groups(term_factors, source),
        function_scores=function_scores,
        function_score_mode=query_fs_meta.get("score_mode"),
        function_boost_mode=query_fs_meta.get("boost_mode"),
        function_score_combined=function_score_combined,
        final_query_score=final_query_score,
    )


def build_filter_matches(request_body: Dict[str, Any], source: Dict[str, Any]) -> List[ExplainFilterRes]:
    results: List[ExplainFilterRes] = []

    bool_query = _extract_bool_query_from_request(request_body)
    filters = bool_query.get("filter", []) if bool_query else []

    for f in filters:
        if "term" in f:
            field, value_obj = next(iter(f["term"].items()))
            value = value_obj.get("value") if isinstance(value_obj, dict) else value_obj

            results.append(ExplainFilterRes(
                label=f"{field} = {value}",
                matched=True,
                source_value=source.get(field),
                description="term filter"
            ))

        elif "range" in f:
            field, range_obj = next(iter(f["range"].items()))
            results.append(ExplainFilterRes(
                label=f"{field} range",
                matched=True,
                source_value=source.get(field),
                description=str(range_obj)
            ))

        elif "bool" in f:
            results.append(ExplainFilterRes(
                label="nested bool filter",
                matched=True,
                description=str(f["bool"])
            ))

        else:
            results.append(ExplainFilterRes(
                label="filter condition",
                matched=True,
                description=str(f)
            ))

    return results

def _find_original_text_query_score(query_expl: Dict[str, Any]) -> Optional[float]:
    """
    query_expl 안에서 function score 적용 전 text score(BM25 aggregate)를 찾는다.
    보통 'sum of:' / 'max of:' / weight(...) 묶음 중 query relevance 부분.
    """
    if not query_expl:
        return None

    # "function score, product of:" 아래 첫 detail이 텍스트 점수인 경우가 많음
    function_score_node = _find_first_node_contains(query_expl, "function score, product of:")
    if function_score_node:
        details = function_score_node.get("details", []) or []
        if details:
            first = details[0]
            if isinstance(first.get("value"), (int, float)):
                return first.get("value")

    return None

def _extract_query_function_score_meta(request_body: Dict[str, Any]) -> Dict[str, Any]:
    query = request_body.get("query", {}) or {}
    fs = query.get("function_score", {}) or {}

    return {
        "score_mode": fs.get("score_mode"),
        "boost_mode": fs.get("boost_mode"),
        "functions": fs.get("functions", []) or [],
    }


def _extract_bool_query_from_request(request_body: Dict[str, Any]) -> Dict[str, Any]:
    query = request_body.get("query", {}) or {}

    if "bool" in query:
        return query["bool"]

    if "function_score" in query:
        fs_query = query["function_score"].get("query", {}) or {}
        if "bool" in fs_query:
            return fs_query["bool"]

    return {}


def build_field_score_groups(
    term_factors: List[ExplainTermFactorRes],
    source: Dict[str, Any]
) -> List[ExplainFieldScoreGroupRes]:
    grouped: Dict[str, ExplainFieldScoreGroupRes] = {}

    for factor in term_factors:
        field_name = factor.field or "unknown"

        if field_name not in grouped:
            grouped[field_name] = ExplainFieldScoreGroupRes(
                field=field_name,
                source_value=source.get(field_name),
                total_score=0.0,
                matched_tokens=[]
            )

        grouped[field_name].matched_tokens.append(
            ExplainMatchedTokenRes(
                token=factor.term or "unknown",
                score=factor.score,
                boost=factor.boost,
                idf=factor.idf,
                tf=factor.tf,
                description=f"freq={factor.freq}, dl={factor.dl}, avgdl={factor.avgdl}"
            )
        )

        grouped[field_name].total_score = (grouped[field_name].total_score or 0.0) + (factor.score or 0.0)

    for item in grouped.values():
        item.matched_tokens.sort(key=lambda x: x.score or 0.0, reverse=True)

    return sorted(grouped.values(), key=lambda x: x.total_score or 0.0, reverse=True)


def build_query_function_scores(
    query_expl: Dict[str, Any],
    request_body: Dict[str, Any],
    source: Dict[str, Any]
) -> List[ExplainFunctionScoreRes]:
    results: List[ExplainFunctionScoreRes] = []

    query = request_body.get("query", {}) or {}
    fs = query.get("function_score", {}) or {}
    functions = fs.get("functions", []) or []

    for idx, fn in enumerate(functions, start=1):
        filter_label = _describe_filter(fn.get("filter"))
        matched_node = _find_matching_function_node(query_expl, filter_label)

        # weight function
        if "weight" in fn:
            results.append(
                ExplainFunctionScoreRes(
                    label=f"Function {idx} - Weight",
                    score=matched_node.get("value") if matched_node else fn.get("weight"),
                    description=matched_node.get("description") if matched_node else "weight function",
                    operation=fs.get("score_mode"),
                    filter_label=filter_label,
                    matched=matched_node is not None,
                    params={"weight": fn.get("weight")}
                )
            )
            continue

        # field_value_factor (query level에도 혹시 있을 수 있으니 처리)
        if "field_value_factor" in fn:
            fvf = fn["field_value_factor"]
            field_name = fvf.get("field")
            results.append(
                ExplainFunctionScoreRes(
                    label=f"Function {idx} - Field Value Factor",
                    score=matched_node.get("value") if matched_node else None,
                    field=field_name,
                    source_value=source.get(field_name),
                    description=matched_node.get("description") if matched_node else "field_value_factor",
                    operation=fs.get("score_mode"),
                    filter_label=filter_label,
                    matched=matched_node is not None,
                    params=fvf
                )
            )
            continue

        # decay function
        for decay_key in ("gauss", "exp", "linear"):
            if decay_key in fn:
                decay_body = fn[decay_key]
                field_name = next(iter(decay_body.keys()))
                results.append(
                    ExplainFunctionScoreRes(
                        label=f"Function {idx} - {decay_key.title()} Decay",
                        score=matched_node.get("value") if matched_node else None,
                        field=field_name,
                        source_value=source.get(field_name),
                        description=matched_node.get("description") if matched_node else f"{decay_key} decay",
                        operation=fs.get("score_mode"),
                        filter_label=filter_label,
                        matched=matched_node is not None,
                        params=decay_body
                    )
                )
                break

    return results


def build_rescore_details(
    rescore_nodes: List[Dict[str, Any]],
    request_body: Dict[str, Any],
    source: Dict[str, Any]
) -> List[ExplainRescoreDetailRes]:
    results: List[ExplainRescoreDetailRes] = []
    request_rescores = request_body.get("rescore", []) or []

    for idx, node in enumerate(rescore_nodes, start=1):
        req_rescore = request_rescores[idx - 1] if idx - 1 < len(request_rescores) else {}

        custom_node = _find_first_node_by_prefix(node, _SCORE_NORMALIZER_PREFIX)
        if custom_node is not None:
            results.append(
                ExplainRescoreDetailRes(
                    order=idx,
                    type="score_normalizer",
                    title=f"Rescore {idx} - Score Normalizer",
                    score=_find_factor_applied_score(custom_node) or custom_node.get("value"),
                    description=f"normalizer={_find_normalizer_type(custom_node)}, factor_mode={_find_factor_mode(custom_node)}",
                    details=[
                        ExplainFunctionScoreRes(
                            label="Original Query Score",
                            score=_find_original_query_score(custom_node),
                            description="normalization 대상 원본 점수"
                        ),
                        ExplainFunctionScoreRes(
                            label="Normalized Score",
                            score=_find_normalized_score(custom_node),
                            description="정규화 후 점수"
                        ),
                        ExplainFunctionScoreRes(
                            label="After Factor",
                            score=_find_factor_applied_score(custom_node),
                            description="factor 적용 후 점수"
                        )
                    ]
                )
            )
            continue

        query_rescore = req_rescore.get("query", {}) or {}
        rescore_query = query_rescore.get("rescore_query", {}) or {}
        fs = rescore_query.get("function_score", {}) or {}
        functions = fs.get("functions", []) or []

        detail_items: List[ExplainFunctionScoreRes] = []

        for f_idx, fn in enumerate(functions, start=1):
            filter_label = _describe_filter(fn.get("filter"))
            matched = _rescore_function_matched(node, filter_label, fn)

            if "field_value_factor" in fn:
                fvf = fn["field_value_factor"]
                field_name = fvf.get("field")
                matched_node = _find_first_node_contains(node, "field value function:")
                detail_items.append(
                    ExplainFunctionScoreRes(
                        label=f"Function {f_idx} - Field Value Factor",
                        score=matched_node.get("value") if matched_node else None,
                        field=field_name,
                        source_value=source.get(field_name),
                        description=matched_node.get("description") if matched_node else "field_value_factor",
                        operation=fs.get("score_mode"),
                        filter_label=filter_label,
                        matched=matched,
                        params=fvf
                    )
                )
                continue

            if "weight" in fn and any(k in fn for k in ("filter",)):
                detail_items.append(
                    ExplainFunctionScoreRes(
                        label=f"Function {f_idx} - Weight",
                        score=fn.get("weight"),
                        description="weight function",
                        operation=fs.get("score_mode"),
                        filter_label=filter_label,
                        matched=matched,
                        params={"weight": fn.get("weight")}
                    )
                )
                continue

            for decay_key in ("gauss", "exp", "linear"):
                if decay_key in fn:
                    decay_body = fn[decay_key]
                    field_name = next(iter(decay_body.keys()))
                    detail_items.append(
                        ExplainFunctionScoreRes(
                            label=f"Function {f_idx} - {decay_key.title()} Decay",
                            score=None,
                            field=field_name,
                            source_value=source.get(field_name),
                            description=f"{decay_key} decay",
                            operation=fs.get("score_mode"),
                            filter_label=filter_label,
                            matched=matched,
                            params=decay_body
                        )
                    )
                    break

        results.append(
            ExplainRescoreDetailRes(
                order=idx,
                type="query_rescore_function_score",
                title=f"Rescore {idx} - Function Score",
                score=node.get("value"),
                description="rescore query의 function_score 결과",
                details=detail_items,
                score_mode=fs.get("score_mode"),
                boost_mode=fs.get("boost_mode"),
                query_weight=query_rescore.get("query_weight"),
                rescore_query_weight=query_rescore.get("rescore_query_weight"),
            )
        )

    return results


# =========================================================
# Explain tree extractors
# =========================================================

def _extract_query_explanation_tree(expl: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not expl:
        return None

    desc = expl.get("description", "") or ""

    if _is_query_root(desc):
        return expl

    original_query_node = _find_first_node_by_exact_description(expl, "original query score")
    if original_query_node:
        details = original_query_node.get("details", []) or []
        if details:
            return details[0]
        return original_query_node

    return None


def _extract_rescore_nodes(expl: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not expl:
        return []

    desc = expl.get("description", "") or ""

    if desc.startswith("sum of:"):
        details = expl.get("details", []) or []
        return [d for d in details if _is_rescore_candidate(d)]

    if desc.startswith(_SCORE_NORMALIZER_PREFIX):
        return [expl]

    return []


def _is_rescore_candidate(node: Dict[str, Any]) -> bool:
    if _find_first_node_by_prefix(node, _SCORE_NORMALIZER_PREFIX) is not None:
        return True

    if _find_first_node_contains(node, "field value function:") is not None:
        return True

    if _find_first_node_contains(node, "secondaryWeight") is not None:
        return True

    if _find_first_node_contains(node, "primaryWeight") is not None:
        return True

    return False


# =========================================================
# Term extraction
# =========================================================

def _extract_term_factors(expl: Dict[str, Any]) -> List[ExplainTermFactorRes]:
    results: List[ExplainTermFactorRes] = []

    def walk(node: Dict[str, Any]):
        desc = node.get("description", "") or ""
        m = re.match(r'weight\(([^:]+):(.+?) in \d+\)', desc)
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
                elif nd.startswith("freq,") or nd.startswith("phrasefreq="):
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
    return description.startswith("weight(") or description.startswith("score(")


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
    target = _find_first_node_by_prefix(node, _SCORE_NORMALIZER_PREFIX)
    if target is not None:
        desc = target.get("description", "") or ""
        m = re.search(r"type=([a-zA-Z0-9_\-]+)", desc)
        if m:
            return m.group(1)

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


def _find_all_nodes_by_exact_description(node: Dict[str, Any], description: str) -> List[Dict[str, Any]]:
    results = []
    if (node.get("description", "") or "") == description:
        results.append(node)

    for child in node.get("details", []) or []:
        results.extend(_find_all_nodes_by_exact_description(child, description))

    return results


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

def _find_matching_function_node(query_expl: Dict[str, Any], filter_label: Optional[str]) -> Optional[Dict[str, Any]]:
    if not query_expl:
        return None

    # match filter: DISP_GRP_CD:1106030200
    if filter_label:
        candidates = _find_all_nodes_contains(query_expl, filter_label)
        if candidates:
            return candidates[0]

    # generic fallback
    node = _find_first_node_contains(query_expl, "match filter:")
    if node is not None:
        return node

    return None

def _describe_filter(filter_obj: Optional[Dict[str, Any]]) -> Optional[str]:
    if not filter_obj:
        return None

    if "term" in filter_obj:
        field, value_obj = next(iter(filter_obj["term"].items()))
        value = value_obj.get("value") if isinstance(value_obj, dict) else value_obj
        return f"{field}:{value}"

    if "match" in filter_obj:
        field, value_obj = next(iter(filter_obj["match"].items()))
        if isinstance(value_obj, dict):
            return f"{field}:{value_obj.get('query')}"
        return f"{field}:{value_obj}"

    if "exists" in filter_obj:
        return f"exists:{filter_obj['exists'].get('field')}"

    if "span_near" in filter_obj:
        return "span_near"

    return str(filter_obj)

def _find_query_function_combined_score(query_expl: Dict[str, Any]) -> Optional[float]:
    """
    query_expl 안에서 function score의 합산 결과를 찾는다.
    예: function score, score mode [sum]
    """
    node = _find_first_node_contains(query_expl, "function score, score mode [")
    if node is not None:
        return node.get("value")
    return None

def _rescore_function_matched(node: Dict[str, Any], filter_label: Optional[str], fn: Dict[str, Any]) -> bool:
    if "field_value_factor" in fn:
        return _find_first_node_contains(node, "field value function:") is not None

    if filter_label:
        if "match filter:" in filter_label:
            return _find_first_node_contains(node, filter_label) is not None

        if _find_first_node_contains(node, filter_label) is not None:
            return True

    if "filter" in fn and "span_near" in fn["filter"]:
        return _find_first_node_contains(node, "span_near") is not None

    if "filter" in fn and "exists" in fn["filter"]:
        field_name = fn["filter"]["exists"].get("field")
        return _find_first_node_contains(node, field_name or "") is not None

    return False