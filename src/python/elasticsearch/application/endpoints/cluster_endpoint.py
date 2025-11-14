import logging, asyncio

from typing import Optional, List, Literal
from fastapi import APIRouter, Request, Query
from starlette.responses import JSONResponse
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR, HTTP_200_OK

from src.python.elasticsearch.application.schemas.responses.common.common_res import CommonRes
from src.python.elasticsearch.application.services.api.cluster_service import ElasticsearchClusterService
from src.python.elasticsearch.config.connections.elasticsearch_connection_manager import get_elasticsearch_client

logger = logging.getLogger(__name__)

router = APIRouter()
cluster_endpoint = router

@router.get("/health", response_model=CommonRes, status_code=200)
async def health(
    request: Request,
    index: Optional[str | List[str] | None] = Query(None, description="건강 상태를 조회할 데이터스트림/인덱스/alias 목록 (없으면 전체)"),
    level: Optional[Literal["cluster", "indices", "shards"] | None] = Query("cluster",description="반환 상세 수준"),
) -> JSONResponse:
    """ Cluster Health API """
    try:
        es_client = get_elasticsearch_client(request.app)

        cluster_service = ElasticsearchClusterService(es_client=es_client)
        result = await cluster_service.health(index=index, level=level)

        return JSONResponse(
            status_code=HTTP_200_OK,
            headers={"Content-Type": "application/json"},
            content=CommonRes(data=result.model_dump(mode="json")).model_dump()
        )

    except Exception as e:
        logger.error(f"Error in Health Check: {e}")
        return JSONResponse(
            status_code=500,
            content=CommonRes(
                code=str(HTTP_500_INTERNAL_SERVER_ERROR),
                message=f"Elasticsearch 관리도구 cluster health 처리 중 오류가 발생했습니다: {str(e)}",
                data=None
            ).model_dump()
        )

