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

    query_meta = _extract_query_function_score_meta(request_body)
    score_mode = query_meta["score_mode"]
    boost_mode = query_meta["boost_mode"]
    functions = query_meta["functions"]

    for idx, fn in enumerate(functions, start=1):
        filter_label = _describe_filter(fn.get("filter"))
        matched_node = _find_matching_function_node(query_expl, filter_label, fn)
        matched = matched_node is not None

        if "weight" in fn:
            applied_score = _extract_applied_function_score(matched_node)

            results.append(
                ExplainFunctionScoreRes(
                    label=f"Function {idx} - Weight",
                    score=applied_score if applied_score is not None else (fn.get("weight") if matched else 0.0),
                    field=None,
                    source_value=None,
                    description=matched_node.get("description") if matched_node is not None else None,
                    operation=score_mode,
                    filter_label=filter_label,
                    matched=matched,
                    params={"weight": fn.get("weight")}
                )
            )
            continue

        if "field_value_factor" in fn:
            fvf = fn["field_value_factor"]
            field_name = fvf.get("field")
            field_node = _find_first_node_contains(query_expl, f"doc['{field_name}']")

            results.append(
                ExplainFunctionScoreRes(
                    label=f"Function {idx} - Field Value Factor",
                    score=field_node.get("value") if field_node else None,
                    field=field_name,
                    source_value=source.get(field_name),
                    description=field_node.get("description") if field_node else None,
                    operation=score_mode,
                    filter_label=filter_label,
                    matched=field_node is not None,
                    params=fvf
                )
            )
            continue

        if "script_score" in fn:
            script_body = fn["script_score"] or {}
            matched_script_node = _find_matching_script_score_node(query_expl, fn)

            results.append(
                ExplainFunctionScoreRes(
                    label=f"Function {idx} - Script Score",
                    score=matched_script_node.get("value") if matched_script_node else None,
                    field=_extract_script_fields(script_body),
                    source_value=_extract_script_source_values(source, script_body),
                    description=matched_script_node.get("description") if matched_script_node else None,
                    operation=score_mode,
                    filter_label=filter_label,
                    matched=matched_script_node is not None,
                    params=script_body,
                )
            )
            continue

        for decay_key in ("gauss", "exp", "linear"):
            if decay_key in fn:
                decay_body = fn[decay_key]
                field_name = next(iter(decay_body.keys()))
                matched_decay_node = _find_first_node_contains(query_expl, f"Function for field {field_name}:")
                matched_decay_value = _extract_first_numeric_leaf_value(matched_decay_node)

                results.append(
                    ExplainFunctionScoreRes(
                        label=f"Function {idx} - {decay_key.title()} Decay",
                        score=matched_decay_value,
                        field=field_name,
                        source_value=source.get(field_name),
                        description=matched_decay_node.get("description") if matched_decay_node else None,
                        operation=score_mode,
                        filter_label=filter_label,
                        matched=matched_decay_node is not None,
                        params=decay_body
                    )
                )
                break

    return results

def normalize_rescores(request_rescores):
    if not request_rescores:
        return []
    if isinstance(request_rescores, dict):
        return [request_rescores]
    if isinstance(request_rescores, list):
        return request_rescores
    return []

def build_rescore_details(
    rescore_nodes: List[Dict[str, Any]],
    request_body: Dict[str, Any],
    source: Dict[str, Any]
) -> List[ExplainRescoreDetailRes]:
    results: List[ExplainRescoreDetailRes] = []
    request_rescores = request_body.get("rescore", []) or []

    for idx, node in enumerate(rescore_nodes, start=1):
        request_rescores = normalize_rescores(request_rescores)

        target_idx = idx - 1
        req_rescore = (
            request_rescores[target_idx]
            if 0 <= target_idx < len(request_rescores)
            else {}
        )

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
                            field=None,
                            source_value=None,
                            description="normalization 대상 원본 점수",
                            operation=None,
                            filter_label=None,
                            matched=True,
                            params=None
                        ),
                        ExplainFunctionScoreRes(
                            label="Normalized Score",
                            score=_find_normalized_score(custom_node),
                            field=None,
                            source_value=None,
                            description="정규화 후 점수",
                            operation=None,
                            filter_label=None,
                            matched=True,
                            params=None
                        ),
                        ExplainFunctionScoreRes(
                            label="After Factor",
                            score=_find_factor_applied_score(custom_node),
                            field=None,
                            source_value=None,
                            description="factor 적용 후 점수",
                            operation=None,
                            filter_label=None,
                            matched=True,
                            params=None
                        )
                    ],
                    score_mode=None,
                    boost_mode=None,
                    query_weight=None,
                    rescore_query_weight=None,
                )
            )
            continue

        meta = _extract_rescore_function_meta(req_rescore)
        score_mode = meta["score_mode"]
        boost_mode = meta["boost_mode"]
        query_weight = meta["query_weight"]
        rescore_query_weight = meta["rescore_query_weight"]
        functions = meta["functions"]

        detail_items: List[ExplainFunctionScoreRes] = []

        combined_node = _find_first_node_contains(node, "function score, score mode [")
        if combined_node is not None:
            detail_items.append(
                ExplainFunctionScoreRes(
                    label="Combined Function Score",
                    score=combined_node.get("value"),
                    field=None,
                    source_value=None,
                    description=f"functions combined by score_mode={score_mode} and applied with boost_mode={boost_mode}",
                    operation=f"score_mode={score_mode}, boost_mode={boost_mode}",
                    filter_label=None,
                    matched=True,
                    params=None
                )
            )

        for f_idx, fn in enumerate(functions, start=1):
            detail_items.append(
                _build_rescore_function_item(
                    node=node,
                    fn=fn,
                    order=f_idx,
                    source=source,
                    score_mode=score_mode,
                    boost_mode=boost_mode,
                )
            )

        results.append(
            ExplainRescoreDetailRes(
                order=idx,
                type="query_rescore_function_score",
                title=f"Rescore {idx} - Function Score",
                score=node.get("value"),
                description=(
                    f"rescore query의 function_score 결과 | "
                    f"query_weight={query_weight}, rescore_query_weight={rescore_query_weight} | "
                    f"score_mode={score_mode}, boost_mode={boost_mode}"
                ),
                details=detail_items,
                score_mode=score_mode,
                boost_mode=boost_mode,
                query_weight=query_weight,
                rescore_query_weight=rescore_query_weight,
            )
        )

    return results

def _extract_rescore_function_meta(req_rescore: Dict[str, Any]) -> Dict[str, Any]:
    query_rescore = req_rescore.get("query", {}) or {}
    rescore_query = query_rescore.get("rescore_query", {}) or {}
    fs = rescore_query.get("function_score", {}) or {}

    return {
        "query_weight": query_rescore.get("query_weight"),
        "rescore_query_weight": query_rescore.get("rescore_query_weight"),
        "score_mode": fs.get("score_mode"),
        "boost_mode": fs.get("boost_mode"),
        "functions": fs.get("functions", []) or [],
    }

def _build_rescore_function_item(
    node: Dict[str, Any],
    fn: Dict[str, Any],
    order: int,
    source: Dict[str, Any],
    score_mode: Optional[str],
    boost_mode: Optional[str],
) -> ExplainFunctionScoreRes:
    filter_label = _describe_filter(fn.get("filter"))
    matched_node = _find_matching_rescore_function_node(node, fn)
    matched = matched_node is not None

    if "field_value_factor" in fn:
        fvf = fn["field_value_factor"]
        field_name = fvf.get("field")
        return ExplainFunctionScoreRes(
            label=f"Function {order} - Field Value Factor",
            score=matched_node.get("value") if matched_node else None,
            field=field_name,
            source_value=source.get(field_name),
            description=_build_function_description(
                base="field_value_factor",
                filter_label=filter_label,
                matched_node=matched_node,
                score_mode=score_mode,
                boost_mode=boost_mode,
                fn_payload=fvf
            ),
            operation=f"score_mode={score_mode}, boost_mode={boost_mode}",
            filter_label=filter_label,
            matched=matched,
            params=fvf
        )

    if "script_score" in fn:
        script_body = fn["script_score"] or {}
        return ExplainFunctionScoreRes(
            label=f"Function {order} - Script Score",
            score=matched_node.get("value") if matched_node else None,
            field=_extract_script_fields(script_body),
            source_value=_extract_script_source_values(source, script_body),
            description=_build_function_description(
                base="script_score",
                filter_label=filter_label,
                matched_node=matched_node,
                score_mode=score_mode,
                boost_mode=boost_mode,
                fn_payload=script_body,
            ),
            operation=f"score_mode={score_mode}, boost_mode={boost_mode}",
            filter_label=filter_label,
            matched=matched,
            params=script_body,
        )

    for decay_key in ("gauss", "exp", "linear"):
        if decay_key in fn:
            decay_body = fn[decay_key]
            field_name = next(iter(decay_body.keys()))
            decay_score = _extract_first_numeric_leaf_value(matched_node)
            return ExplainFunctionScoreRes(
                label=f"Function {order} - {decay_key.title()} Decay",
                score=decay_score,
                field=field_name,
                source_value=source.get(field_name),
                description=_build_function_description(
                    base=f"{decay_key} decay",
                    filter_label=filter_label,
                    matched_node=matched_node,
                    score_mode=score_mode,
                    boost_mode=boost_mode,
                    fn_payload=decay_body
                ),
                operation=f"score_mode={score_mode}, boost_mode={boost_mode}",
                filter_label=filter_label,
                matched=matched,
                params=decay_body
            )

    if "weight" in fn:
        applied_score = _extract_applied_function_score(matched_node)
        return ExplainFunctionScoreRes(
            label=f"Function {order} - Weight",
            score=applied_score if applied_score is not None else (fn.get("weight") if matched else 0.0),
            field=None,
            source_value=None,
            description=_build_function_description(
                base="weight function",
                filter_label=filter_label,
                matched_node=matched_node,
                score_mode=score_mode,
                boost_mode=boost_mode,
                fn_payload={"weight": fn.get("weight")}
            ),
            operation=f"score_mode={score_mode}, boost_mode={boost_mode}",
            filter_label=filter_label,
            matched=matched,
            params={"weight": fn.get("weight")}
        )

    return ExplainFunctionScoreRes(
        label=f"Function {order} - Unknown",
        score=matched_node.get("value") if matched_node else None,
        field=None,
        source_value=None,
        description=_build_function_description(
            base="unknown function",
            filter_label=filter_label,
            matched_node=matched_node,
            score_mode=score_mode,
            boost_mode=boost_mode,
            fn_payload=fn
        ),
        operation=f"score_mode={score_mode}, boost_mode={boost_mode}",
        filter_label=filter_label,
        matched=matched,
        params=fn
    )

def _find_matching_rescore_function_node(
    node: Dict[str, Any],
    fn: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    if "field_value_factor" in fn:
        field_name = fn["field_value_factor"].get("field")
        if field_name:
            return _find_first_node_contains(node, f"doc['{field_name}']")

    if "script_score" in fn:
        return _find_matching_script_score_node(node, fn)

    if "filter" in fn:
        filter_obj = fn["filter"]

        if "term" in filter_obj:
            filter_label = _describe_filter(filter_obj)
            exact = _find_first_node_contains(node, f"match filter: {filter_label}")
            if exact is not None:
                return _find_parent_function_score_product(node, exact)

        if "exists" in filter_obj:
            field_name = filter_obj["exists"].get("field")
            exact = _find_first_node_contains(node, f"FieldExistsQuery [field={field_name}]")
            if exact is None:
                exact = _find_first_node_contains(node, f"ConstantScore(FieldExistsQuery [field={field_name}])")
            if exact is not None:
                return _find_parent_function_score_product(node, exact)

        if "match" in filter_obj:
            # explain 상 match filter는 쿼리 rewrite 되어 길게 나오므로
            # field명 기반으로 느슨하게 찾는다.
            match_body = filter_obj["match"]
            field_name = next(iter(match_body.keys()))
            candidates = _find_all_nodes_contains(node, "match filter:")
            for candidate in candidates:
                desc = candidate.get("description", "") or ""
                if field_name in desc:
                    return _find_parent_function_score_product(node, candidate)

        if "span_near" in filter_obj:
            span_near = filter_obj["span_near"]
            slop = span_near.get("slop")
            clauses = span_near.get("clauses", []) or []

            expected_terms: List[str] = []
            for clause in clauses:
                if "span_term" in clause:
                    span_field, span_value = next(iter(clause["span_term"].items()))
                    expected_terms.append(f"{span_field}:{span_value}")

            candidates = _find_all_nodes_contains(node, "spanNear(")
            for candidate in candidates:
                desc = candidate.get("description", "") or ""
                if f", {slop}," in desc and all(term in desc for term in expected_terms):
                    return _find_parent_function_score_product(node, candidate)

    for decay_key in ("gauss", "exp", "linear"):
        if decay_key in fn:
            field_name = next(iter(fn[decay_key].keys()))
            return _find_first_node_contains(node, f"Function for field {field_name}:")

    return None

def _build_function_description(
    base: str,
    filter_label: Optional[str],
    matched_node: Optional[Dict[str, Any]],
    score_mode: Optional[str],
    boost_mode: Optional[str],
    fn_payload: Optional[Dict[str, Any]]
) -> str:
    parts: List[str] = [base]

    if filter_label:
        parts.append(f"filter={filter_label}")

    if fn_payload:
        parts.append(f"params={fn_payload}")

    if score_mode or boost_mode:
        parts.append(f"score_mode={score_mode}, boost_mode={boost_mode}")

    if matched_node is not None:
        parts.append(f"explain={matched_node.get('description')}")

    return " | ".join(parts)

def _extract_applied_function_score(node: Optional[Dict[str, Any]]) -> Optional[float]:
    if node is None:
        return None

    desc = node.get("description", "") or ""

    # 일반적인 function score, product of:
    if desc.startswith("function score, product of:"):
        details = node.get("details", []) or []

        # 구조:
        # - match filter: ...
        # - product of:
        #   - constant score 1.0 - no function provided
        #   - weight
        if len(details) >= 2:
            product_of = details[1]
            if (product_of.get("description", "") or "").startswith("product of:"):
                product_children = product_of.get("details", []) or []
                if len(product_children) >= 2:
                    return product_children[1].get("value")

        return node.get("value")

    return node.get("value")

def _extract_first_numeric_leaf_value(node: Optional[Dict[str, Any]]) -> Optional[float]:
    if node is None:
        return None

    details = node.get("details", []) or []
    if not details:
        return node.get("value")

    for child in details:
        value = _extract_first_numeric_leaf_value(child)
        if value is not None:
            return value

    return node.get("value")

def _find_parent_function_score_product(root: Dict[str, Any], target: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    def walk(node: Dict[str, Any], parents: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if node is target:
            for parent in reversed(parents):
                desc = parent.get("description", "") or ""
                if desc.startswith("function score, product of:"):
                    return parent
            return target

        for child in node.get("details", []) or []:
            found = walk(child, parents + [node])
            if found is not None:
                return found
        return None

    return walk(root, [])

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

def _find_matching_script_score_node(
    node: Dict[str, Any],
    fn: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    script_body = fn.get("script_score", {}) or {}
    script = script_body.get("script", {}) or {}

    # 1순위: 설명 prefix로 직접 찾기
    exact = _find_first_node_contains(node, "script score function, computed with script:")
    if exact is not None:
        return exact

    # 2순위: script source 일부로 찾기
    source = script.get("source") or script.get("idOrCode")
    if source:
        snippet = str(source)[:40]
        exact = _find_first_node_contains(node, snippet)
        if exact is not None:
            return exact

    # 3순위: params나 doc['FIELD'] 기반으로 찾기
    fields = _extract_script_field_names(script)
    for field in fields:
        exact = _find_first_node_contains(node, f"doc['{field}']")
        if exact is not None:
            parent = _find_parent_function_score_product(node, exact)
            return parent or exact

    return None

def _extract_script_field_names(script_obj: Dict[str, Any]) -> List[str]:
    script_source = (
        script_obj.get("source")
        or script_obj.get("idOrCode")
        or ""
    )
    return list(dict.fromkeys(re.findall(r"doc\[['\"]([^'\"]+)['\"]\]", str(script_source))))

def _extract_script_fields(script_score_obj: Dict[str, Any]) -> Optional[str]:
    script = script_score_obj.get("script", {}) or script_score_obj
    fields = _extract_script_field_names(script)
    if not fields:
        return None
    return ", ".join(fields)

def _extract_script_source_values(
    source: Dict[str, Any],
    script_score_obj: Dict[str, Any]
) -> Optional[Any]:
    script = script_score_obj.get("script", {}) or script_score_obj
    fields = _extract_script_field_names(script)
    if not fields:
        return None

    if len(fields) == 1:
        return source.get(fields[0])

    return {field: source.get(field) for field in fields}

def _find_matching_function_node(
    query_expl: Dict[str, Any],
    filter_label: Optional[str],
    fn: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    if not query_expl:
        return None

    # 1. term filter는 exact match만 허용
    if "filter" in fn and "term" in fn["filter"]:
        if filter_label:
            exact = _find_first_node_contains(query_expl, f"match filter: {filter_label}")
            if exact is not None:
                return _find_parent_function_score_product(query_expl, exact)
        return None

    # 2. exists filter
    if "filter" in fn and "exists" in fn["filter"]:
        field_name = fn["filter"]["exists"].get("field")
        exact = _find_first_node_contains(query_expl, f"FieldExistsQuery [field={field_name}]")
        if exact is None:
            exact = _find_first_node_contains(query_expl, f"ConstantScore(FieldExistsQuery [field={field_name}])")
        if exact is not None:
            return _find_parent_function_score_product(query_expl, exact)
        return None

    # 3. match filter
    if "filter" in fn and "match" in fn["filter"]:
        match_body = fn["filter"]["match"]
        field_name = next(iter(match_body.keys()))
        candidates = _find_all_nodes_contains(query_expl, "match filter:")
        for candidate in candidates:
            desc = candidate.get("description", "") or ""
            if field_name in desc:
                return _find_parent_function_score_product(query_expl, candidate)
        return None

    # 4. span_near
    if "filter" in fn and "span_near" in fn["filter"]:
        span_near = fn["filter"]["span_near"]
        slop = span_near.get("slop")
        clauses = span_near.get("clauses", []) or []

        expected_terms: List[str] = []
        for clause in clauses:
            if "span_term" in clause:
                span_field, span_value = next(iter(clause["span_term"].items()))
                expected_terms.append(f"{span_field}:{span_value}")

        candidates = _find_all_nodes_contains(query_expl, "spanNear(")
        for candidate in candidates:
            desc = candidate.get("description", "") or ""
            if f", {slop}," in desc and all(term in desc for term in expected_terms):
                return _find_parent_function_score_product(query_expl, candidate)
        return None

    # 5. field_value_factor
    if "field_value_factor" in fn:
        field_name = fn["field_value_factor"].get("field")
        if field_name:
            return _find_first_node_contains(query_expl, f"doc['{field_name}']")
        return None

    # 6. Script Score
    if "script_score" in fn:
        return _find_matching_script_score_node(query_expl, fn)

    # 7. decay
    for decay_key in ("gauss", "exp", "linear"):
        if decay_key in fn:
            field_name = next(iter(fn[decay_key].keys()))
            return _find_first_node_contains(query_expl, f"Function for field {field_name}:")

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
            return f"{field} match:{value_obj.get('query')}"
        return f"{field} match:{value_obj}"

    if "exists" in filter_obj:
        return f"exists:{filter_obj['exists'].get('field')}"

    if "span_near" in filter_obj:
        clauses = filter_obj["span_near"].get("clauses", []) or []
        terms: List[str] = []

        for clause in clauses:
            if "span_term" in clause:
                span_field, span_value = next(iter(clause["span_term"].items()))
                terms.append(f"{span_field}:{span_value}")

        slop = filter_obj["span_near"].get("slop")
        in_order = filter_obj["span_near"].get("in_order")
        return f"span_near[{', '.join(terms)}], slop={slop}, in_order={in_order}"

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
