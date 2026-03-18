import logging

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR

from src.python.elasticsearch.application.schemas.responses.common.common_res import CommonRes
from src.python.elasticsearch.application.schemas.requests.search.search_explain_req import SearchExplainSummaryReq, SearchExplainDetailReq
from src.python.elasticsearch.application.services.api.search_explain_service import SearchExplainService
from src.python.elasticsearch.config.connections.elasticsearch_connection_manager import get_elasticsearch_client

logger = logging.getLogger(__name__)

router = APIRouter()
search_explain_endpoint = router


@router.post("/summary", response_model=CommonRes, status_code=200)
async def explain_summary(request: Request, body: SearchExplainSummaryReq) -> JSONResponse:
    try:
        es_client = get_elasticsearch_client(request.app)
        service = SearchExplainService(es_client=es_client)
        result = await service.search_explain_summary(body)

        return JSONResponse(
            status_code=HTTP_200_OK,
            headers={"Content-Type": "application/json"},
            content=CommonRes(data=result.model_dump(mode="json")).model_dump()
        )
    except Exception as e:
        logger.exception("Error in explain summary")
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content=CommonRes(
                code=str(HTTP_500_INTERNAL_SERVER_ERROR),
                message=f"Explain Summary 처리 중 오류가 발생했습니다: {str(e)}",
                data=None
            ).model_dump()
        )


@router.post("/detail", response_model=CommonRes, status_code=200)
async def explain_detail(request: Request, body: SearchExplainDetailReq) -> JSONResponse:
    try:
        es_client = get_elasticsearch_client(request.app)
        service = SearchExplainService(es_client=es_client)
        result = await service.search_explain_detail(body)

        return JSONResponse(
            status_code=HTTP_200_OK,
            headers={"Content-Type": "application/json"},
            content=CommonRes(data=result.model_dump(mode="json")).model_dump()
        )
    except Exception as e:
        logger.exception("Error in explain detail")
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content=CommonRes(
                code=str(HTTP_500_INTERNAL_SERVER_ERROR),
                message=f"Explain Detail 처리 중 오류가 발생했습니다: {str(e)}",
                data=None
            ).model_dump()
        )