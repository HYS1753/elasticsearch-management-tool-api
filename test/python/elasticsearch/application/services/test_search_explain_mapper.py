import pytest
from typing import Any, Dict
from src.python.elasticsearch.application.services.mapper.search_explain_mapper import (
    _parse_query_structure,
    _extract_term_factors,
    _parse_summary_from_explanation,
    summarize_hit,
    build_detail
)
from src.python.elasticsearch.application.schemas.responses.search.search_explain_res import QueryStructureNode

@pytest.fixture
def mock_node() -> Dict[str, Any]:
    return {
        "value": 1.2,
        "description": "sum of:",
        "details": [
            {
                "value": 0.8,
                "description": "weight(content:hello in 123)",
                "details": []
            }
        ]
    }

@pytest.fixture
def mock_request_body() -> Dict[str, Any]:
    return {"knn": {"field": "vector_field"}}

def test_parse_query_structure_sum_of(mock_node: Dict[str, Any]):
    result = _parse_query_structure(mock_node)
    assert result is not None
    assert result.type == "sum_of"
    assert result.description == "sum of:"
    assert result.value == 1.2
    assert len(result.details) == 1
    assert result.details[0].type == "bm25"
    assert result.details[0].field == "content"
    assert result.details[0].term == "hello"

def test_parse_query_structure_max_of(mock_node: Dict[str, Any]):
    mock_node["description"] = "max of plus 0.1 times others of:"
    result = _parse_query_structure(mock_node)
    assert result is not None
    assert result.type == "max_of"
    assert result.tie_breaker == 0.1

def test_parse_query_structure_knn(mock_request_body: Dict[str, Any]):
    mock_knn_node = {
        "value": 0.9,
        "description": "cosine similarity",
        "details": []
    }
    result = _parse_query_structure(mock_knn_node, mock_request_body)
    assert result is not None
    assert result.type == "knn"
    assert result.field == "vector_field"

def test_parse_query_structure_bm25(mock_node: Dict[str, Any]):
    bm25_node = mock_node["details"][0]
    result = _parse_query_structure(bm25_node)
    assert result is not None
    assert result.type == "bm25"
    assert result.field == "content"
    assert result.term == "hello"

def test_parse_query_structure_bm25_with_suffix():
    node1 = {
        "value": 4.28,
        "description": "weight(PRD_NM.plain:tv in 822) [PerFieldSimilarity], result of:",
        "details": []
    }
    node2 = {
        "value": 8.13,
        "description": "weight(GOODS_NM.plain:tv) [PerFieldSimilarity], result of:",
        "details": []
    }
    res1 = _parse_query_structure(node1)
    res2 = _parse_query_structure(node2)
    assert res1 is not None
    assert res1.type == "bm25"
    assert res1.field == "PRD_NM.plain"
    assert res1.term == "tv"
    
    assert res2 is not None
    assert res2.type == "bm25"
    assert res2.field == "GOODS_NM.plain"
    assert res2.term == "tv"

def test_parse_query_structure_constantscore(mock_node: Dict[str, Any]):
    mock_node["description"] = "ConstantScore(content:hello)"
    result = _parse_query_structure(mock_node)
    assert result is not None
    assert result.type == "constant_score"

@pytest.fixture
def mock_expl() -> Dict[str, Any]:
    return {
        "value": 1.2,
        "description": "sum of:",
        "details": [
            {
                "value": 0.8,
                "description": "weight(content:hello in 123)",
                "details": [
                    {"value": 1.5, "description": "tf, computed as..."},
                    {"value": 2.0, "description": "idf, computed as..."}
                ]
            },
            {
                "value": 0.9,
                "description": "within [0, 1] cosine similarity",
                "details": []
            }
        ]
    }

def test_extract_term_factors(mock_expl: Dict[str, Any], mock_request_body: Dict[str, Any]):
    result = _extract_term_factors(mock_expl, mock_request_body)
    assert len(result) == 2
    
    # BM25 term
    assert result[0].field == "content"
    assert result[0].term == "hello"
    assert result[0].score == 0.8
    assert result[0].tf == 1.5
    assert result[0].idf == 2.0
    
    # KNN term
    assert result[1].field == "vector_field"
    assert result[1].term == "[Vector]"
    assert result[1].score == 0.9

def test_parse_summary_from_explanation_sum():
    expl = {
        "value": 2.5,
        "description": "sum of:",
        "details": [
            {"value": 1.5, "description": "weight(title:test)"},
            {"value": 1.0, "description": "weight(body:test)"}
        ]
    }
    result = _parse_summary_from_explanation(expl)
    assert result["query_score"] == 2.5
    assert len(result["rescore_steps"]) == 0

def test_parse_summary_from_explanation_max():
    expl = {
        "value": 1.5,
        "description": "max of:",
        "details": [
            {"value": 1.5, "description": "weight(title:test)"},
            {"value": 1.0, "description": "weight(body:test)"}
        ]
    }
    result = _parse_summary_from_explanation(expl)
    assert result["query_score"] == 1.5
    assert len(result["rescore_steps"]) == 0

def test_parse_summary_from_explanation_rescore():
    expl = {
        "value": 3.0,
        "description": "sum of:",
        "details": [
            {
                "value": 2.0,
                "description": "original query score",
            },
            {
                "value": 1.0,
                "description": "score_normalizer_rescore.normalized_score[type=min_max]",
                "details": [
                    {
                        "value": 1.0,
                        "description": "score_normalizer_rescore.factor_applied_score[mode=multiply]"
                    }
                ]
            }
        ]
    }
    result = _parse_summary_from_explanation(expl)
    assert result["query_score"] == 2.0
    assert len(result["rescore_steps"]) == 1
    assert result["rescore_steps"][0].value == 3.0
    assert result["rescore_steps"][0].operator_value == 1.0
    assert result["rescore_steps"][0].operator == "->"
    assert "min_max" in result["rescore_steps"][0].label


def test_parse_summary_from_explanation_multiple_nested_rescores():
    expl = {
        "value": 3.025,
        "description": "sum of:",
        "details": [
            {
                "value": 3.0,
                "description": "original query score",
                "details": [
                    {
                        "value": 3.0,
                        "description": "sum of:",
                        "details": [
                            {
                                "value": 3.0,
                                "description": "score_normalizer_rescore.normalized_score[type=min_max]",
                                "details": [
                                    {
                                        "value": 10.0,
                                        "description": "original query score",
                                        "details": [
                                            {
                                                "value": 10.0,
                                                "description": "weight(title:test)"
                                            }
                                        ]
                                    },
                                    {
                                        "value": 3.0,
                                        "description": "score_normalizer_rescore.factor_applied_score[mode=multiply]"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                "value": 0.025,
                "description": "function score, product of:",
                "details": []
            }
        ]
    }
    result = _parse_summary_from_explanation(expl)
    assert result["query_score"] == 10.0
    assert len(result["rescore_steps"]) == 2
    
    assert result["rescore_steps"][0].value == 3.0
    assert result["rescore_steps"][0].operator_value == 3.0
    assert "min_max" in result["rescore_steps"][0].label
    
    assert result["rescore_steps"][1].value == 3.025
    assert result["rescore_steps"][1].operator_value == 0.025
    assert result["rescore_steps"][1].operator == "+"



def test_parse_summary_from_explanation_function_score():
    expl = {
        "value": 82.81142,
        "description": "function score, product of:",
        "details": [
            {
                "value": 16.562283,
                "description": "sum of:",
                "details": [
                    {
                        "value": 8.136316,
                        "description": "max of:"
                    }
                ]
            },
            {
                "value": 5.0,
                "description": "product of:",
                "details": []
            }
        ]
    }
    result = _parse_summary_from_explanation(expl)
    assert result["query_score"] == 16.562283
    assert len(result["rescore_steps"]) == 1
    assert result["rescore_steps"][0].key == "query_function_score"
    assert result["rescore_steps"][0].value == 82.81142
    assert result["rescore_steps"][0].formula_label == "function_score"


def test_build_score_timeline_function_score():
    from src.python.elasticsearch.application.services.mapper.search_explain_mapper import build_score_timeline
    expl = {
        "value": 82.81142,
        "description": "function score, product of:",
        "details": [
            {
                "value": 16.562283,
                "description": "sum of:",
                "details": [
                    {
                        "value": 8.136316,
                        "description": "max of:"
                    }
                ]
            },
            {
                "value": 5.0,
                "description": "product of:",
                "details": []
            }
        ]
    }
    steps = build_score_timeline(expl, total_score=82.81142)
    assert len(steps) == 3
    assert steps[0].key == "query"
    assert steps[0].value == 16.562283
    assert steps[1].key == "function_score"
    assert steps[1].value == 82.81142
    assert "x5.00" in steps[1].description
    assert steps[2].key == "total"
    assert steps[2].value == 82.81142


def test_parse_query_structure_new_combining_types():
    # Test min of
    node_min = {"value": 1.5, "description": "min of:", "details": []}
    res_min = _parse_query_structure(node_min)
    assert res_min.type == "min_of"

    # Test mean of / avg of
    node_mean = {"value": 2.5, "description": "mean of:", "details": []}
    res_mean = _parse_query_structure(node_mean)
    assert res_mean.type == "mean_of"

    node_avg = {"value": 2.5, "description": "avg of:", "details": []}
    res_avg = _parse_query_structure(node_avg)
    assert res_avg.type == "mean_of"

    # Test product of
    node_prod = {"value": 3.0, "description": "product of:", "details": []}
    res_prod = _parse_query_structure(node_prod)
    assert res_prod.type == "product_of"


def test_parse_query_structure_robust_bm25():
    # Test nested span query
    node_span = {"value": 2.1, "description": "weight(span(GOODS_NM.span:4도어) in doc)", "details": []}
    res_span = _parse_query_structure(node_span)
    assert res_span.type == "bm25"
    assert res_span.field == "GOODS_NM.span"
    assert res_span.term == "4도어"

    # Test BM25 with quotes
    node_quotes = {"value": 3.2, "description": 'weight(content:"hello world" in 123)', "details": []}
    res_quotes = _parse_query_structure(node_quotes)
    assert res_quotes.type == "bm25"
    assert res_quotes.field == "content"
    assert res_quotes.term == "hello world"

    # Test BM25 normal
    node_normal = {"value": 1.2, "description": "weight(PRD_NM.plain:tv) [PerFieldSimilarity]", "details": []}
    res_normal = _parse_query_structure(node_normal)
    assert res_normal.type == "bm25"
    assert res_normal.field == "PRD_NM.plain"
    assert res_normal.term == "tv"


