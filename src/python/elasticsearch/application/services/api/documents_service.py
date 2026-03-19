from elasticsearch import AsyncElasticsearch

from src.python.elasticsearch.application.repository.elasticsearch.cat_repository import (
    ElasticsearchCatRepository,
)
from src.python.elasticsearch.application.repository.elasticsearch.documents_repository import (
    ElasticsearchDocumentsRepository,
)
from src.python.elasticsearch.application.schemas.requests.documents.document_search_req import (
    DocumentSearchReq,
)
from src.python.elasticsearch.application.schemas.responses.documents.document_indices_res import (
    DocumentIndexItem,
    DocumentIndicesRes,
)
from src.python.elasticsearch.application.schemas.responses.documents.document_search_res import (
    DocumentHitItem,
    DocumentSearchRes,
)


class DocumentsService:
    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def get_document_indices(self) -> DocumentIndicesRes:
        cat_repository = ElasticsearchCatRepository(self.es_client)

        indices_infos = await cat_repository.get_indices_info(exclude_hidden=True)

        items = [
            DocumentIndexItem(
                index=item.index,
                health=item.health,
                status=item.status,
                docs_count=item.docs_count,
                store_size=item.store_size,
            )
            for item in indices_infos.indices
        ]

        return DocumentIndicesRes(indices=items)

    async def search_documents(
        self,
        search_req: DocumentSearchReq,
    ) -> DocumentSearchRes:
        documents_repository = ElasticsearchDocumentsRepository(self.es_client)

        response = await documents_repository.search_documents(
            index_name=search_req.index_name,
            query=search_req.query,
            from_=search_req.from_,
            size=search_req.size,
            sort=search_req.sort,
        )

        hits_section = response.get("hits", {})
        raw_hits = hits_section.get("hits", [])
        total_info = hits_section.get("total", 0)

        if isinstance(total_info, dict):
            total = int(total_info.get("value", 0))
        else:
            total = int(total_info)

        hits = [
            DocumentHitItem(
                _index=item.get("_index", ""),
                _id=item.get("_id", ""),
                _score=item.get("_score"),
                _source=item.get("_source", {}),
                sort=item.get("sort"),
            )
            for item in raw_hits
        ]

        return DocumentSearchRes(
            took=int(response.get("took", 0)),
            timed_out=bool(response.get("timed_out", False)),
            total=total,
            hits=hits,
        )