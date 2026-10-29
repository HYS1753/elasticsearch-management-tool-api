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
    QueryStructureNode,
    ScoreSubDetail,
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

    score_timeline = build_score_timeline(explanation, hit.get("_score"), request_body)

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

    # Extract original query explanation and rescore nodes using the traverse helper
    query_expl, rescore_nodes = _traverse_rescore_explanation(expl)
    
    # 1. Base query score (before any function score or rescores)
    query_score = query_expl.get("value") if query_expl else final_score
    if query_score is None:
        query_score = final_score
        
    rescore_steps: List[ExplainScoreStepRes] = []
    
    # 2. Add rescore steps
    for idx, node in enumerate(rescore_nodes, start=1):
        context = node.get("_rescore_context", {})
        combining_desc = context.get("combining_desc", "")
        combining_value = context.get("combining_value")
        
        # Determine operator
        op = "+"
        if "product of:" in combining_desc.lower() or "multiplied by:" in combining_desc.lower():
            op = "*"
        elif "max of:" in combining_desc.lower():
            op = "max"
        elif "min of:" in combining_desc.lower():
            op = "min"
        elif "mean of:" in combining_desc.lower() or "avg of:" in combining_desc.lower() or "average of:" in combining_desc.lower():
            op = "avg"
            
        custom_node = _find_first_node_by_prefix(node, _SCORE_NORMALIZER_PREFIX)
        if custom_node is not None:
            # Custom normalizer step
            normalizer_type = _find_normalizer_type(custom_node) or "unknown"
            val = _find_factor_applied_score(custom_node) or node.get("value") or 0.0
            
            rescore_steps.append(
                ExplainScoreStepRes(
                    key=f"rescore_{idx}_score_normalizer_normalized",
                    label=f"score_normalizer:{normalizer_type}",
                    value=combining_value if combining_value is not None else val,
                    formula_label=f"rescore{idx}:normalize({normalizer_type})",
                    operator="->",
                    operator_value=val
                )
            )
        else:
            # Standard rescore step
            val = node.get("value") or 0.0
            desc = node.get("description", "") or ""
            
            # Check for field value function
            field_value_node = _find_first_node_contains(node, "field value function:")
            if field_value_node is not None:
                label = "query_rescore:field_value_factor"
                formula_label = f"rescore{idx}:field_value_factor"
            else:
                function_score_node = _find_first_node_contains(node, "function score")
                if function_score_node is not None:
                    label = "query_rescore:function_score"
                    formula_label = f"rescore{idx}:function_score"
                else:
                    label = f"rescore:{desc[:30]}" if desc else f"rescore{idx}"
                    formula_label = f"rescore{idx}"
                    
            rescore_steps.append(
                ExplainScoreStepRes(
                    key=f"rescore_{idx}_generic",
                    label=label,
                    value=combining_value if combining_value is not None else val,  # Combined total score after this step
                    formula_label=formula_label,
                    operator=op,
                    operator_value=val  # The contribution of the rescore query itself
                )
            )
            
    parsed = {
        "query_score": query_score,
        "rescore_steps": rescore_steps
    }

    # 3. Resolve original query score vs function score for the main query
    if query_expl:
        original_text_score = _find_original_text_query_score(query_expl)
        if original_text_score is not None:
            parsed["query_score"] = original_text_score
            final_query_score = query_expl.get("value") or 0.0
            
            # Detect function score operator from description
            fs_node = _find_function_score_node(query_expl)
            fs_desc = fs_node.get("description", "").lower() if fs_node else ""
            fs_op = "*"
            if "sum of:" in fs_desc:
                fs_op = "+"
            elif "min of:" in fs_desc:
                fs_op = "min"
            elif "max of:" in fs_desc:
                fs_op = "max"
            elif "replace" in fs_desc:
                fs_op = "->"
                
            multiplier = 1.0
            if fs_op == "*":
                if original_text_score != 0:
                    multiplier = final_query_score / original_text_score
            elif fs_op == "+":
                multiplier = final_query_score - original_text_score
            else:
                multiplier = final_query_score

            fs_step = ExplainScoreStepRes(
                key="query_function_score",
                label="function_score",
                value=final_query_score,
                formula_label="function_score",
                operator=fs_op,
                operator_value=multiplier
            )
            parsed["rescore_steps"].insert(0, fs_step)

    return parsed


def _parse_max_root_summary(
    expl: Dict[str, Any],
    final_score: Optional[float] = None
) -> Dict[str, Any]:
    details = expl.get("details", []) or []

    query_score = _find_original_query_score(expl)
    rescore_steps: List[ExplainScoreStepRes] = []

    rescore_idx = 1
    for d in details:
        steps = _parse_rescore_step_node(d, rescore_idx, parent_op="max")
        if steps:
            rescore_steps.extend(steps)
            rescore_idx += 1

    if query_score is None:
        if not rescore_steps:
            query_score = expl.get("value")
        else:
            query_score = _find_original_query_score(expl)

    return {
        "query_score": query_score,
        "rescore_steps": rescore_steps
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
                formula_label=f"normalize({normalizer_type or 'unknown'})",
                operator="->",
                operator_value=normalized_score
            )
        )

    if factor_applied_score is not None:
        rescore_steps.append(
            ExplainScoreStepRes(
                key="score_normalizer_factor_applied",
                label=f"score_normalizer_factor:{factor_mode or 'unknown'}",
                value=factor_applied_score,
                formula_label=f"factor({factor_mode or 'unknown'})",
                operator="->",
                operator_value=factor_applied_score
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

    rescore_idx = 1
    for d in details:
        steps = _parse_rescore_step_node(d, rescore_idx, parent_op="+")
        if steps:
            rescore_steps.extend(steps)
            rescore_idx += 1

    if query_score is None:
        if not rescore_steps:
            query_score = expl.get("value")
        else:
            query_score = _find_original_query_score(expl)

    return {
        "query_score": query_score,
        "rescore_steps": rescore_steps
    }


def _parse_rescore_step_node(node: Dict[str, Any], idx: int, parent_op: str = "+") -> List[ExplainScoreStepRes]:
    desc = node.get("description", "") or ""
    if desc == "original query score":
        return []

    desc_lower = desc.lower()
    if (
        desc.startswith("weight(")
        or desc.startswith("score(")
        or "constantscore" in desc_lower
        or "constant score" in desc_lower
        or any(x in desc_lower for x in ["knn", "cosine similarity", "dot product", "l2", "within [0, 1]"])
    ):
        return []


    custom_node = _find_first_node_by_prefix(node, _SCORE_NORMALIZER_PREFIX)
    if custom_node is not None:
        normalizer_type = _find_normalizer_type(custom_node)
        factor_applied_score = _find_factor_applied_score(custom_node)
        normalized_score = _find_normalized_score(custom_node)
        factor_mode = _find_factor_mode(custom_node)

        steps = []
        if normalized_score is not None:
            steps.append(ExplainScoreStepRes(
                key=f"rescore_{idx}_score_normalizer_normalized",
                label=f"score_normalizer:{normalizer_type or 'unknown'}",
                value=normalized_score,
                formula_label=f"rescore{idx}:normalize({normalizer_type or 'unknown'})",
                operator="->",
                operator_value=normalized_score
            ))
        if factor_applied_score is not None:
            steps.append(ExplainScoreStepRes(
                key=f"rescore_{idx}_score_normalizer_factor_applied",
                label=f"score_normalizer_factor:{factor_mode or 'unknown'}",
                value=factor_applied_score,
                formula_label=f"rescore{idx}:factor({factor_mode or 'unknown'})",
                operator="->",
                operator_value=factor_applied_score
            ))
        return steps

    field_value_node = _find_first_node_contains(node, "field value function:")
    if field_value_node is not None:
        val = node.get("value")
        return [ExplainScoreStepRes(
            key=f"rescore_{idx}_field_value_factor",
            label="query_rescore:field_value_factor",
            value=val,
            formula_label=f"rescore{idx}:field_value_factor",
            operator=parent_op,
            operator_value=val
        )]

    function_score_node = _find_first_node_contains(node, "function score")
    if function_score_node is not None:
        val = node.get("value")
        return [ExplainScoreStepRes(
            key=f"rescore_{idx}_function_score",
            label="query_rescore:function_score",
            value=val,
            formula_label=f"rescore{idx}:function_score",
            operator=parent_op,
            operator_value=val
        )]

    val = node.get("value")
    if val is not None and desc:
        return [ExplainScoreStepRes(
            key=f"rescore_{idx}_generic",
            label=f"rescore:{desc}",
            value=val,
            formula_label=f"rescore{idx}",
            operator=parent_op,
            operator_value=val
        )]

    return []


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
        expr_parts: List[str] = []
        for idx, step in enumerate(valid_steps):
            label = step.formula_label or step.label or f"rescore{idx+1}"
            op = step.operator or "->"
            step_str = f"{label}({step.value:.4f})"
            if idx == 0:
                expr_parts.append(step_str)
            else:
                expr_parts.append(f"{op} {step_str}")
        formula = " ".join(expr_parts)
        if total_score is not None:
            formula += f" = total({float(total_score):.4f})"
        return formula

    expr_parts = [f"query({query_score:.4f})"]
    for idx, step in enumerate(valid_steps):
        label = step.formula_label or step.label or f"rescore{idx+1}"
        op = step.operator or "->"
        op_val = step.operator_value if step.operator_value is not None else step.value
        if label == "function_score":
            expr_parts.append(f"* boost({op_val:.4f})")
        else:
            expr_parts.append(f"{op} {label}({step.value:.4f})")
            
    formula = " ".join(expr_parts)
    if total_score is not None:
        formula += f" = total({float(total_score):.4f})"
    return formula


# =========================================================
# Detail parsing
# =========================================================

def _build_query_sub_details(
    query_expl: Optional[Dict[str, Any]],
    request_body: Optional[Dict[str, Any]] = None
) -> List[ScoreSubDetail]:
    """Build field-level sub_details for the query timeline step.
    
    Groups BM25 term factors by field and detects clause_type from
    the request body's bool query structure.
    """
    if not query_expl:
        return []

    term_factors = _extract_term_factors(query_expl, request_body)
    if not term_factors:
        return []

    # Determine clause membership for each field from request_body
    field_clause_map = _build_field_clause_map(request_body)

    # Group by field
    grouped: Dict[str, List[ExplainTermFactorRes]] = {}
    for factor in term_factors:
        field_name = factor.field or "unknown"
        if field_name not in grouped:
            grouped[field_name] = []
        grouped[field_name].append(factor)

    sub_details: List[ScoreSubDetail] = []
    for field_name, factors in grouped.items():
        total_score = sum(f.score or 0.0 for f in factors)
        tokens = [f.term or "?" for f in factors if f.term]
        clause_type = field_clause_map.get(field_name, "must")

        # Build human-readable description
        token_parts = []
        for f in factors:
            token_label = f.term or "?"
            score_val = f.score or 0.0
            token_parts.append(f'"{token_label}" +{score_val:.2f}')
        desc = ", ".join(token_parts) if token_parts else None

        sub_details.append(ScoreSubDetail(
            field=field_name,
            score=total_score,
            tokens=tokens,
            clause_type=clause_type,
            description=desc
        ))

    # Sort by score desc
    sub_details.sort(key=lambda x: x.score or 0.0, reverse=True)
    return sub_details


def _build_field_clause_map(request_body: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Map field names to their bool clause type (must/should/filter/knn)."""
    result: Dict[str, str] = {}
    if not request_body:
        return result

    # Check for KNN fields
    knn_obj = request_body.get("knn")
    if isinstance(knn_obj, dict):
        knn_field = knn_obj.get("field")
        if knn_field:
            result[knn_field] = "knn"
    elif isinstance(knn_obj, list):
        for k in knn_obj:
            if isinstance(k, dict):
                knn_field = k.get("field")
                if knn_field:
                    result[knn_field] = "knn"

    # Extract bool query clauses
    bool_query = _extract_bool_query_from_request(request_body)
    if not bool_query:
        return result

    for clause_type in ("must", "should", "filter"):
        clauses = bool_query.get(clause_type, [])
        if isinstance(clauses, dict):
            clauses = [clauses]
        for clause in clauses:
            fields = _extract_fields_from_clause(clause)
            for f in fields:
                if f not in result:
                    result[f] = clause_type

    return result


def _extract_fields_from_clause(clause: Dict[str, Any]) -> List[str]:
    """Extract field names from a single bool clause (match, term, multi_match, etc.)."""
    fields: List[str] = []
    if not isinstance(clause, dict):
        return fields

    if "match" in clause:
        fields.extend(clause["match"].keys())
    elif "match_phrase" in clause:
        fields.extend(clause["match_phrase"].keys())
    elif "term" in clause:
        fields.extend(clause["term"].keys())
    elif "terms" in clause:
        fields.extend(clause["terms"].keys())
    elif "multi_match" in clause:
        mm_fields = clause["multi_match"].get("fields", [])
        for f in mm_fields:
            # Strip boost notation like "field^2"
            clean = f.split("^")[0].strip()
            if clean:
                fields.append(clean)
    elif "dis_max" in clause:
        for q in clause["dis_max"].get("queries", []):
            fields.extend(_extract_fields_from_clause(q))
    elif "bool" in clause:
        for sub_clause_type in ("must", "should"):
            sub_clauses = clause["bool"].get(sub_clause_type, [])
            if isinstance(sub_clauses, dict):
                sub_clauses = [sub_clauses]
            for sc in sub_clauses:
                fields.extend(_extract_fields_from_clause(sc))

    return fields


def build_score_timeline(
    expl: Dict[str, Any],
    total_score: Optional[float],
    request_body: Optional[Dict[str, Any]] = None
) -> List[QueryExplainScoreTimelineStepRes]:
    steps: List[QueryExplainScoreTimelineStepRes] = []

    # Get query explanation and rescore nodes
    query_expl, rescore_nodes = _traverse_rescore_explanation(expl)

    # Build sub_details for the query step from term factors
    query_sub_details = _build_query_sub_details(query_expl, request_body)

    # 1. Add original text query score and function score if present
    original_text_score = None
    if query_expl:
        original_text_score = _find_original_text_query_score(query_expl)

    if original_text_score is not None:
        steps.append(QueryExplainScoreTimelineStepRes(
            key="query",
            label="Original Query Score",
            value=original_text_score,
            description="검색어 매칭으로 계산된 원본 점수",
            operator=None,
            operator_value=None,
            sub_details=query_sub_details
        ))
        
        final_query_score = query_expl.get("value") or 0.0
        
        # Detect function score operator from description
        fs_node = _find_function_score_node(query_expl)
        fs_desc = fs_node.get("description", "").lower() if fs_node else ""
        fs_op = "*"
        if "sum of:" in fs_desc:
            fs_op = "+"
        elif "min of:" in fs_desc:
            fs_op = "min"
        elif "max of:" in fs_desc:
            fs_op = "max"
        elif "replace" in fs_desc:
            fs_op = "->"
            
        multiplier = 1.0
        if fs_op == "*":
            if original_text_score != 0:
                multiplier = final_query_score / original_text_score
            op_desc = f"x{multiplier:.4f}"
        elif fs_op == "+":
            multiplier = final_query_score - original_text_score
            op_desc = f"+{multiplier:.4f}"
        else:
            multiplier = final_query_score
            op_desc = f"-> {multiplier:.4f}"
            
        steps.append(QueryExplainScoreTimelineStepRes(
            key="function_score",
            label="Function Score",
            value=final_query_score,
            description=f"가중치 함수 적용 결과 (배율: {op_desc})",
            operator=fs_op,
            operator_value=multiplier
        ))
    else:
        original_query_score = query_expl.get("value") if query_expl else None
        if original_query_score is None and expl.get("value") is not None and _is_query_root(expl.get("description", "")):
            original_query_score = expl.get("value")
            
        if original_query_score is not None:
            steps.append(QueryExplainScoreTimelineStepRes(
                key="query",
                label="Original Query Score",
                value=original_query_score,
                description="검색어 매칭으로 계산된 원본 점수",
                operator=None,
                operator_value=None,
                sub_details=query_sub_details
            ))

    # 2. Add rescore steps
    for idx, node in enumerate(rescore_nodes, start=1):
        context = node.get("_rescore_context", {})
        combining_desc = context.get("combining_desc", "")
        combining_value = context.get("combining_value")
        
        # Determine operator
        op = "+"
        if "product of:" in combining_desc.lower() or "multiplied by:" in combining_desc.lower():
            op = "*"
        elif "max of:" in combining_desc.lower():
            op = "max"
        elif "min of:" in combining_desc.lower():
            op = "min"
        elif "mean of:" in combining_desc.lower() or "avg of:" in combining_desc.lower() or "average of:" in combining_desc.lower():
            op = "avg"

        custom_node = _find_first_node_by_prefix(node, _SCORE_NORMALIZER_PREFIX)
        if custom_node is not None:
            normalizer_type = _find_normalizer_type(custom_node) or "unknown"
            val = _find_factor_applied_score(custom_node) or node.get("value") or 0.0
            card_val = combining_value if combining_value is not None else val
            
            steps.append(QueryExplainScoreTimelineStepRes(
                key=f"rescore_{idx}_normalizer",
                label=f"Rescore {idx}",
                value=card_val,
                description=f"score_normalizer:{normalizer_type}",
                operator="->",
                operator_value=val
            ))
            continue

        val = node.get("value") or 0.0
        desc = node.get("description", "") or ""
        card_val = combining_value if combining_value is not None else val
        
        steps.append(QueryExplainScoreTimelineStepRes(
            key=f"rescore_{idx}",
            label=f"Rescore {idx}",
            value=card_val,
            description=desc,
            operator=op,
            operator_value=val
        ))

    if total_score is not None:
        steps.append(QueryExplainScoreTimelineStepRes(
            key="total",
            label="Total Score",
            value=total_score,
            description="최종 점수",
            operator=None,
            operator_value=None
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
            query_structure=None,
        )

    term_factors = _extract_term_factors(query_expl, request_body)
    function_scores = build_query_function_scores(
        query_expl=query_expl,
        request_body=request_body,
        source=source
    )

    original_score = _find_original_text_query_score(query_expl)
    final_query_score = query_expl.get("value") if query_expl.get("value") is not None else fallback_score
    if original_score is None:
        original_score = final_query_score

    function_score_combined = _find_query_function_combined_score(query_expl)
    if function_score_combined is None and original_score is not None and final_query_score is not None:
        if original_score != 0 and abs(final_query_score - original_score) > 1e-5:
            function_score_combined = final_query_score / original_score

    query_structure = _parse_query_structure(query_expl, request_body)

    return ExplainQueryDetailRes(
        original_score=original_score,
        filters=build_filter_matches(request_body, source),
        bm25_groups=build_field_score_groups(term_factors, source),
        function_scores=function_scores,
        function_score_mode=query_fs_meta.get("score_mode"),
        function_boost_mode=query_fs_meta.get("boost_mode"),
        function_score_combined=function_score_combined,
        final_query_score=final_query_score,
        query_structure=query_structure,
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

def _find_function_score_node(node: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not node:
        return None
    desc = node.get("description", "") or ""
    if "function score" in desc.lower():
        return node
    for child in node.get("details", []) or []:
        found = _find_function_score_node(child)
        if found is not None:
            return found
    return None


def _find_original_text_query_score(query_expl: Dict[str, Any]) -> Optional[float]:
    """
    query_expl 안에서 function score 적용 전 text score(BM25 aggregate)를 찾는다.
    보통 'sum of:' / 'max of:' / weight(...) 묶음 중 query relevance 부분.
    """
    if not query_expl:
        return None

    fs_node = _find_function_score_node(query_expl)
    if fs_node:
        details = fs_node.get("details", []) or []
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
                freq=factor.freq,
                dl=factor.dl,
                avgdl=factor.avgdl,
                n_val=factor.n_val,
                N_val=factor.N_val,
                k1=factor.k1,
                b=factor.b,
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
            filter_field, filter_source_value = _extract_filter_field_and_source_value(
                source=source,
                filter_obj=fn.get("filter")
            )

            results.append(
                ExplainFunctionScoreRes(
                    label=f"Function {idx} - Weight",
                    score=applied_score if applied_score is not None else (fn.get("weight") if matched else 0.0),
                    field=filter_field,
                    source_value=filter_source_value,
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

                matched_decay_parent = _find_matching_function_node(query_expl, filter_label, fn)
                matched_decay_node = _find_decay_value_node(matched_decay_parent, field_name)

                results.append(
                    ExplainFunctionScoreRes(
                        label=f"Function {idx} - {decay_key.title()} Decay",
                        score=matched_decay_parent.get("value") if matched_decay_parent else None,
                        field=field_name,
                        source_value=source.get(field_name),
                        description=matched_decay_node.get("description") if matched_decay_node else None,
                        operation=score_mode,
                        filter_label=filter_label,
                        matched=matched_decay_parent is not None,
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

def combining_desc_to_score_mode(desc: str) -> str:
    if not desc:
        return "total"
    desc_lower = desc.lower()
    if "product of:" in desc_lower or "multiplied by:" in desc_lower:
        return "multiply"
    if "max of:" in desc_lower:
        return "max"
    if "min of:" in desc_lower:
        return "min"
    if "mean of:" in desc_lower or "avg of:" in desc_lower or "average of:" in desc_lower:
        return "avg"
    return "total"


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

        context = node.get("_rescore_context", {})
        combining_desc = context.get("combining_desc", "")
        combined_score = context.get("combining_value")
        if combined_score is None:
            combined_score = node.get("value")
        rescore_query_score = node.get("value")

        custom_node = _find_first_node_by_prefix(node, _SCORE_NORMALIZER_PREFIX)
        if custom_node is not None:
            normalizer_type = _find_normalizer_type(custom_node) or "unknown"
            results.append(
                ExplainRescoreDetailRes(
                    order=idx,
                    type="score_normalizer",
                    title=f"Rescore {idx} - Score Normalizer",
                    score=combined_score,
                    rescore_query_score=rescore_query_score,
                    rescore_query_structure=_parse_query_structure(node, request_body),
                    description=f"normalizer={normalizer_type}, factor_mode={_find_factor_mode(custom_node)}",
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
                    score_mode=req_rescore.get("score_mode") or "total",
                    boost_mode=None,
                    query_weight=req_rescore.get("query", {}).get("query_weight", 1.0),
                    rescore_query_weight=req_rescore.get("query", {}).get("rescore_query_weight", 1.0),
                )
            )
            continue

        meta = _extract_rescore_function_meta(req_rescore)
        score_mode = meta["score_mode"] or combining_desc_to_score_mode(combining_desc) or "total"
        boost_mode = meta["boost_mode"]
        query_weight = meta["query_weight"] if meta["query_weight"] is not None else 1.0
        rescore_query_weight = meta["rescore_query_weight"] if meta["rescore_query_weight"] is not None else 1.0
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

        rescore_query_structure = _parse_query_structure(node, request_body)

        results.append(
            ExplainRescoreDetailRes(
                order=idx,
                type="query_rescore_function_score" if functions else "query_rescore",
                title=f"Rescore {idx} - Function Score" if functions else f"Rescore {idx} - Match/Query Rescore",
                score=combined_score,
                rescore_query_score=rescore_query_score,
                rescore_query_structure=rescore_query_structure,
                description=(
                    f"rescore query 결과 | "
                    f"query_weight={query_weight}, rescore_query_weight={rescore_query_weight} | "
                    f"score_mode={score_mode}" + (f", boost_mode={boost_mode}" if boost_mode else "")
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
        "score_mode": req_rescore.get("score_mode"),
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

            # 실제 UI score 는 raw decay 값이 아니라
            # weight 까지 적용된 function score 결과를 보여줘야 한다.
            decay_value_node = _find_decay_value_node(matched_node, field_name)
            applied_decay_score = matched_node.get("value") if matched_node is not None else None

            return ExplainFunctionScoreRes(
                label=f"Function {order} - {decay_key.title()} Decay",
                score=applied_decay_score,
                field=field_name,
                source_value=source.get(field_name),
                description=_build_function_description(
                    base=f"{decay_key} decay",
                    filter_label=filter_label,
                    matched_node=decay_value_node or matched_node,
                    score_mode=score_mode,
                    boost_mode=boost_mode,
                    fn_payload=decay_body
                ),
                operation=f"score_mode={score_mode}, boost_mode={boost_mode}",
                filter_label=filter_label,
                matched=matched_node is not None,
                params=decay_body
            )

    if "weight" in fn:
        applied_score = _extract_applied_function_score(matched_node)
        filter_field, filter_source_value = _extract_filter_field_and_source_value(
            source=source,
            filter_obj=fn.get("filter")
        )

        return ExplainFunctionScoreRes(
            label=f"Function {order} - Weight",
            score=applied_score if applied_score is not None else (fn.get("weight") if matched else 0.0),
            field=filter_field,
            source_value=filter_source_value,
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

        if "terms" in filter_obj:
            field_name, values = next(iter(filter_obj["terms"].items()))
            if isinstance(values, list):
                matched_parent = _find_terms_filter_parent(node, field_name, values)
                if matched_parent is not None:
                    return matched_parent

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

            # 1순위: explain 에 spanNear(...) 가 그대로 남아있는 경우
            candidates = _find_all_nodes_contains(node, "spanNear(")
            for candidate in candidates:
                desc = candidate.get("description", "") or ""
                if f", {slop}," in desc and all(term in desc for term in expected_terms):
                    return _find_parent_function_score_product(node, candidate)

            # 2순위: explain 이 rewrite 되어 match filter: FIELD:TERM 으로 나온 경우
            return _find_span_near_rewritten_parent(
                node=node,
                expected_terms=expected_terms,
                target_weight=fn.get("weight"),
            )

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

def _find_terms_filter_parent(
    node: Dict[str, Any],
    field_name: str,
    values: List[Any],
) -> Optional[Dict[str, Any]]:
    if not field_name or not values:
        return None

    candidates = _find_all_nodes_contains(node, "match filter:")
    expected_values = {str(v) for v in values}

    for candidate in candidates:
        desc = candidate.get("description", "") or ""

        if f"match filter: {field_name}:(" not in desc:
            continue

        m = re.search(rf"match filter: {re.escape(field_name)}:\((.*?)\)", desc)
        if not m:
            continue

        actual_values = set(token.strip() for token in m.group(1).split() if token.strip())

        if actual_values == expected_values:
            parent = _find_parent_function_score_product(node, candidate)
            return parent or candidate

    return None

def _find_decay_value_node(
    node: Optional[Dict[str, Any]],
    field_name: str,
) -> Optional[Dict[str, Any]]:
    if node is None or not field_name:
        return None

    exact = _find_first_node_contains(node, f"Function for field {field_name}:")
    if exact is not None:
        return exact

    candidates = _find_all_nodes_contains(node, "Function for field ")
    for candidate in candidates:
        desc = candidate.get("description", "") or ""
        if f"field {field_name}:" in desc:
            return candidate

    return None


def _float_equals(a: Optional[float], b: Optional[float], tol: float = 1e-6) -> bool:
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


def _node_contains_all_terms(
    node: Optional[Dict[str, Any]],
    terms: List[str],
) -> bool:
    if node is None:
        return False

    desc = node.get("description", "") or ""
    for term in terms:
        if term in desc:
            continue
        if _find_first_node_contains(node, term) is None:
            return False

    return True


def _find_span_near_rewritten_parent(
    node: Dict[str, Any],
    expected_terms: List[str],
    target_weight: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    # 1차: rewrite 된 match filter 노드 기준 탐색
    rewritten_candidates = _find_all_nodes_contains(node, "match filter:")
    for candidate in rewritten_candidates:
        parent = _find_parent_function_score_product(node, candidate)
        if parent is None:
            continue

        if not _node_contains_all_terms(parent, expected_terms):
            continue

        if target_weight is not None:
            applied_score = _extract_applied_function_score(parent)
            if not _float_equals(applied_score, target_weight):
                continue

        return parent

    # 2차: function score product 단위 전체 탐색
    product_candidates = _find_all_nodes_contains(node, "function score, product of:")
    for candidate in product_candidates:
        if not _node_contains_all_terms(candidate, expected_terms):
            continue

        if target_weight is not None:
            applied_score = _extract_applied_function_score(candidate)
            if not _float_equals(applied_score, target_weight):
                continue

        return candidate

    return None


# =========================================================
# Explain tree extractors
# =========================================================

def _is_rescore_root(node: Dict[str, Any]) -> bool:
    if not node:
        return False
    details = node.get("details", []) or []
    return any(d.get("description") == "original query score" for d in details)


def _find_shallowest_original_query_node(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not node:
        return None
    queue = [node]
    while queue:
        curr = queue.pop(0)
        details = curr.get("details", []) or []
        for d in details:
            if d.get("description") == "original query score":
                return d
            queue.append(d)
    return None


def _find_previous_score_node(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not node:
        return None
    details = node.get("details", []) or []
    # 1. Check direct children for "original query score"
    for d in details:
        if d.get("description") == "original query score":
            return d
    # 2. Check direct children for score normalizer prefix
    for d in details:
        desc = d.get("description", "") or ""
        if desc.startswith(_SCORE_NORMALIZER_PREFIX):
            return d
    # 3. Fallback to recursive BFS search
    return _find_shallowest_original_query_node(node)


def _traverse_rescore_explanation(node: Dict[str, Any]) -> tuple[Dict[str, Any], list[Dict[str, Any]]]:
    if not node:
        return {}, []

    # Find the previous score node under node
    orig_node = _find_previous_score_node(node)

    if orig_node is not None:
        # If orig_node is found, recursively traverse its details to get the base query tree
        orig_details = orig_node.get("details", []) or []
        if orig_details:
            inner_expl, inner_steps = _traverse_rescore_explanation(orig_details[0])
        else:
            inner_expl, inner_steps = orig_node, []

        # Determine the rescore step node(s) for the current level
        details = node.get("details", []) or []
        is_direct_child = any(d is orig_node for d in details)

        if is_direct_child:
            desc = orig_node.get("description", "") or ""
            if desc.startswith(_SCORE_NORMALIZER_PREFIX):
                # If the previous score node is a normalizer, it is a custom step itself
                step_nodes = [orig_node]
            else:
                step_nodes = [d for d in details if d is not orig_node]
        else:
            # Custom nested rescore (like score_normalizer): the current node itself is the step node
            step_nodes = [node]

        combining_desc = node.get("description", "") or ""
        combining_value = node.get("value")

        annotated_step_nodes = []
        for s_node in step_nodes:
            annotated = dict(s_node)
            annotated["_rescore_context"] = {
                "combining_desc": combining_desc,
                "combining_value": combining_value,
                "original_query_score": orig_node.get("value")
            }
            annotated_step_nodes.append(annotated)

        return inner_expl, inner_steps + annotated_step_nodes

    return node, []


def _extract_query_explanation_tree(expl: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    query_expl, _ = _traverse_rescore_explanation(expl)
    return query_expl


def _extract_rescore_nodes(expl: Dict[str, Any]) -> List[Dict[str, Any]]:
    _, rescore_nodes = _traverse_rescore_explanation(expl)
    return rescore_nodes



# =========================================================
# Term extraction
# =========================================================

def _extract_term_factors(
    expl: Dict[str, Any],
    request_body: Optional[Dict[str, Any]] = None
) -> List[ExplainTermFactorRes]:
    results: List[ExplainTermFactorRes] = []

    def walk(node: Dict[str, Any]):
        desc = node.get("description", "") or ""
        
        # 1. BM25 weight
        m = re.match(r'weight\(([^:]+):(.+?)(?:\s+in\s+\d+)?\)', desc)
            
        if m:
            field = m.group(1)
            term = m.group(2)
            score = node.get("value")

            factor = ExplainTermFactorRes(field=field, term=term, score=score)

            def walk_term(n: Dict[str, Any]):
                desc_raw = n.get("description", "") or ""
                nd = desc_raw.lower()
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
                elif desc_raw.startswith("n, "):
                    factor.n_val = n.get("value")
                elif desc_raw.startswith("N, "):
                    factor.N_val = n.get("value")
                elif desc_raw.startswith("k1, "):
                    factor.k1 = n.get("value")
                elif desc_raw.startswith("b, "):
                    factor.b = n.get("value")

                for c in n.get("details", []) or []:
                    walk_term(c)

            walk_term(node)
            results.append(factor)
            return

        # 2. KNN similarity
        elif any(x in desc.lower() for x in ["knn", "cosine similarity", "dot product", "l2", "within [0, 1]"]):
            field = None
            m_field = re.search(r"field:\s*([a-zA-Z0-9_\-]+)", desc)
            if m_field:
                field = m_field.group(1)
            else:
                field = _find_knn_field_from_request(request_body)

            if field:
                factor = ExplainTermFactorRes(
                    field=field,
                    term="[Vector]",
                    score=node.get("value"),
                    boost=1.0,
                    idf=1.0,
                    tf=1.0,
                    freq=1.0,
                    dl=1.0,
                    avgdl=1.0
                )
                results.append(factor)
                return

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
    desc_lower = description.lower()
    return (
        description.startswith("weight(")
        or description.startswith("score(")
        or description.startswith("max of")
        or "knn" in desc_lower
        or "cosine similarity" in desc_lower
        or "dot product" in desc_lower
        or "l2" in desc_lower
        or "within [0, 1]" in desc_lower
    )


def _parse_query_structure(
    node: Optional[Dict[str, Any]],
    request_body: Optional[Dict[str, Any]] = None
) -> Optional[QueryStructureNode]:
    if not node:
        return None

    desc = node.get("description", "") or ""
    val = node.get("value", 0.0)

    node_type = "unknown"
    field = None
    term = None
    tie_breaker = None

    if desc.startswith("sum of:"):
        node_type = "sum_of"
    elif desc.startswith("max of"):
        node_type = "max_of"
        m = re.search(r"max of plus\s+([0-9.]+)\s+times", desc)
        if m:
            tie_breaker = float(m.group(1))
        else:
            tie_breaker = 0.0
    elif desc.startswith("min of:"):
        node_type = "min_of"
    elif desc.startswith("mean of:") or desc.startswith("avg of:") or desc.startswith("average of:"):
        node_type = "mean_of"
    elif desc.startswith("product of:") or desc.startswith("multiplied by:"):
        node_type = "product_of"
    elif any(x in desc.lower() for x in ["knn", "cosine similarity", "dot product", "l2", "within [0, 1]"]):
        node_type = "knn"
        m = re.search(r"field:\s*([a-zA-Z0-9_\-]+)", desc)
        if m:
            field = m.group(1)
        else:
            field = _find_knn_field_from_request(request_body)
        term = "[Vector]"
    elif desc.startswith("weight(") or desc.startswith("score("):
        node_type = "bm25"
        # Split on first colon to extract field and term robustly (handles span queries and other wrappers)
        if ":" in desc:
            parts = desc.split(":", 1)
            left, right = parts[0].strip(), parts[1].strip()
            m_field = re.search(r'([a-zA-Z0-9_\.\-]+)$', left)
            if m_field:
                field = m_field.group(1)
            
            if right.startswith('"'):
                m_term = re.match(r'^"([^"]+)"', right)
                if m_term:
                    term = m_term.group(1)
            else:
                m_term = re.match(r'^([^)\s]+)', right)
                if m_term:
                    term = m_term.group(1)
        
        if not field or not term:
            m = re.match(r'weight\(([^:]+):(.+?)(?:\s+in\s+\d+)?\)', desc)
            if m:
                field = m.group(1)
                term = m.group(2)
            else:
                node_type = "weight"
    elif "function score" in desc.lower():
        node_type = "function_score"
    elif "constantscore" in desc.lower() or "constant score" in desc.lower():
        node_type = "constant_score"

    details = node.get("details", []) or []
    child_nodes = []
    for d in details:
        child = _parse_query_structure(d, request_body)
        if child:
            child_nodes.append(child)

    return QueryStructureNode(
        type=node_type,
        description=desc,
        value=val,
        field=field,
        term=term,
        tie_breaker=tie_breaker,
        details=child_nodes
    )


def _find_knn_field_from_request(request_body: Optional[Dict[str, Any]]) -> Optional[str]:
    if not request_body:
        return None

    knn_obj = request_body.get("knn")
    if isinstance(knn_obj, dict):
        return knn_obj.get("field")
    elif isinstance(knn_obj, list) and len(knn_obj) > 0 and isinstance(knn_obj[0], dict):
        return knn_obj[0].get("field")

    query_obj = request_body.get("query", {})
    if isinstance(query_obj, dict):
        inner_knn = query_obj.get("knn")
        if isinstance(inner_knn, dict):
            return inner_knn.get("field")
        elif isinstance(inner_knn, list) and len(inner_knn) > 0 and isinstance(inner_knn[0], dict):
            return inner_knn[0].get("field")

    return None


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

def _normalize_source_field_name(field_name: Optional[str]) -> Optional[str]:
    if not field_name:
        return None

    # span 전용 서브필드는 원본 source 필드명으로 되돌린다.
    # 예: GOODS_NM.span -> GOODS_NM
    if field_name.endswith(".span"):
        return field_name[:-5]

    return field_name


def _extract_filter_field_and_source_value(
    source: Dict[str, Any],
    filter_obj: Optional[Dict[str, Any]]
) -> (Optional[str], Optional[Any]):
    if not filter_obj:
        return None, None

    if "term" in filter_obj:
        field_name = next(iter(filter_obj["term"].keys()))
        source_field = _normalize_source_field_name(field_name)
        return source_field, source.get(source_field)

    if "terms" in filter_obj:
        field_name = next(iter(filter_obj["terms"].keys()))
        source_field = _normalize_source_field_name(field_name)
        return source_field, source.get(source_field)

    if "span_near" in filter_obj:
        clauses = filter_obj["span_near"].get("clauses", []) or []
        span_fields: List[str] = []

        for clause in clauses:
            if "span_term" in clause:
                span_field = next(iter(clause["span_term"].keys()))
                normalized = _normalize_source_field_name(span_field)
                if normalized and normalized not in span_fields:
                    span_fields.append(normalized)

        if not span_fields:
            return None, None

        if len(span_fields) == 1:
            field_name = span_fields[0]
            return field_name, source.get(field_name)

        return ", ".join(span_fields), {field: source.get(field) for field in span_fields}

    return None, None

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

    # 1-2. terms filter
    if "filter" in fn and "terms" in fn["filter"]:
        field_name, values = next(iter(fn["filter"]["terms"].items()))
        if isinstance(values, list):
            matched_parent = _find_terms_filter_parent(query_expl, field_name, values)
            if matched_parent is not None:
                return matched_parent
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

        # 1순위: explain 에 spanNear(...) 가 그대로 남아있는 경우
        candidates = _find_all_nodes_contains(query_expl, "spanNear(")
        for candidate in candidates:
            desc = candidate.get("description", "") or ""
            if f", {slop}," in desc and all(term in desc for term in expected_terms):
                return _find_parent_function_score_product(query_expl, candidate)

        # 2순위: explain 이 rewrite 된 경우
        return _find_span_near_rewritten_parent(
            node=query_expl,
            expected_terms=expected_terms,
            target_weight=fn.get("weight"),
        )

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

    if "terms" in filter_obj:
        field, values = next(iter(filter_obj["terms"].items()))
        if isinstance(values, list):
            joined = ", ".join(str(v) for v in values)
            return f"{field} in [{joined}]"
        return f"{field} in {values}"

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
    if not query_expl:
        return None

    node = _find_first_node_contains(query_expl, "function score, score mode [")
    if node is not None:
        return node.get("value")

    fs_node = _find_function_score_node(query_expl)
    if fs_node:
        details = fs_node.get("details", []) or []
        node_val = fs_node.get("value")
        if len(details) >= 2:
            return details[1].get("value")
        elif len(details) == 1:
            first_val = details[0].get("value")
            if node_val is not None and first_val is not None and first_val != 0:
                if abs(node_val - first_val) > 1e-5:
                    return node_val / first_val

    return None
