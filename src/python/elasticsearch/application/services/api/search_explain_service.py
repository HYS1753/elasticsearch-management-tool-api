from elasticsearch import AsyncElasticsearch

from src.python.elasticsearch.application.repository.elasticsearch.explain_repository import ElasticsearchSearchExaplainRepository
from src.python.elasticsearch.application.schemas.requests.search.search_explain_req import SearchExplainSummaryReq, SearchExplainDetailReq
from src.python.elasticsearch.application.schemas.responses.search.search_explain_res import SearchExplainSummaryRes
from src.python.elasticsearch.application.services.mapper.search_explain_mapper import summarize_hit, build_detail


class SearchExplainService:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client
        self.repository = ElasticsearchSearchExaplainRepository(es_client)

    async def search_explain_summary(self, req: SearchExplainSummaryReq) -> SearchExplainSummaryRes:
        response = await self.repository.search_with_explain(index=req.index, body=req.body)

        hits = response.get("hits", {}).get("hits", [])
        total = response.get("hits", {}).get("total")
        total_value = total.get("value") if isinstance(total, dict) else total

        return SearchExplainSummaryRes(
            took=response.get("took", 0),
            timed_out=response.get("timed_out", False),
            total_hits=total_value,
            hits=[
                summarize_hit(
                    hit,
                    include_source_fields=req.include_source_fields,
                    doc_title_fields=req.doc_title_fields
                )
                for hit in hits
            ]
        )

    async def search_explain_detail(self, req: SearchExplainDetailReq):
        response = await self.repository.search_with_explain(index=req.index, body=req.body)
        hits = response.get("hits", {}).get("hits", [])

        target_hit = next((hit for hit in hits if hit.get("_id") == req.doc_id), None)
        if target_hit is None:
            raise ValueError(f"doc_id={req.doc_id} 문서를 검색 결과에서 찾을 수 없습니다.")

        return build_detail(
            target_hit,
            request_body=req.body,
            doc_title_fields=req.doc_title_fields,
            include_source_fields=req.include_source_fields,
            include_raw_explain=req.include_raw_explain
        )