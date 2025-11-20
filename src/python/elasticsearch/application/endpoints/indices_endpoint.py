import logging

from fastapi import APIRouter, Request, Query
from starlette.responses import JSONResponse
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR, HTTP_200_OK

from src.python.elasticsearch.application.schemas.responses.common.common_res import CommonRes
from src.python.elasticsearch.application.services.api.indices_service import IndicesService
from src.python.elasticsearch.config.connections.elasticsearch_connection_manager import get_elasticsearch_client

logger = logging.getLogger(__name__)

router = APIRouter()
indices_endpoint = router

@router.get("/indices-placement", response_model=CommonRes, status_code=200)
async def indices_placement(request: Request,
                            include_hidden_index: bool = Query(default=False, description="숨김 인덱스 포함 여부"),
                            include_closed_index: bool = Query(default=False, description="닫힌 인덱스 포함 여부")
                            ) -> JSONResponse:
    """ Indices Placement API """
    try:
        es_client = get_elasticsearch_client(request.app)

        cluster_service = IndicesService(es_client=es_client)
        result = await cluster_service.indices_placement(include_hidden_index=include_hidden_index,
                                                         include_closed_index=include_closed_index)

        return JSONResponse(
            status_code=HTTP_200_OK,
            headers={"Content-Type": "application/json"},
            content=CommonRes(data=result.model_dump(mode="json")).model_dump()
        )

    except Exception as e:
        logger.error(f"Error in Indices Placement Check: {e}")
        return JSONResponse(
            status_code=500,
            content=CommonRes(
                code=str(HTTP_500_INTERNAL_SERVER_ERROR),
                message=f"Elasticsearch 관리도구 Indices Placement 처리 중 오류가 발생했습니다: {str(e)}",
                data=None
            ).model_dump()
        )