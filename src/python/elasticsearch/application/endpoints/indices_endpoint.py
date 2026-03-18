import logging

from fastapi import APIRouter, Query, Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR

from src.python.elasticsearch.application.schemas.responses.common.common_res import CommonRes
from src.python.elasticsearch.application.services.api.indices_service import IndicesService
from src.python.elasticsearch.config.connections.elasticsearch_connection_manager import get_elasticsearch_client
from src.python.elasticsearch.config.exceptions.biz_exceptions import BizException

logger = logging.getLogger(__name__)

router = APIRouter()
indices_endpoint = router


@router.get("/indices-placement", response_model=CommonRes, status_code=200)
async def indices_placement(
    request: Request,
    include_hidden_index: bool = Query(default=False, description="숨김 인덱스 포함 여부"),
    include_closed_index: bool = Query(default=False, description="닫힌 인덱스 포함 여부"),
) -> JSONResponse:
    try:
        es_client = get_elasticsearch_client(request.app)
        indices_service = IndicesService(es_client=es_client)

        result = await indices_service.indices_placement(
            include_hidden_index=include_hidden_index,
            include_closed_index=include_closed_index,
        )

        return JSONResponse(
            status_code=HTTP_200_OK,
            headers={"Content-Type": "application/json"},
            content=CommonRes(data=result.model_dump(mode="json")).model_dump(),
        )
    except BizException as e:
        logger.error(f"Error in Indices Placement Check: {e}")
        return JSONResponse(
            status_code=e.status_code,
            content=CommonRes(
                code=str(e.status_code),
                message=e.message,
                data=None,
            ).model_dump(),
        )
    except Exception as e:
        logger.error(f"Error in Indices Placement Check: {e}")
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content=CommonRes(
                code=str(HTTP_500_INTERNAL_SERVER_ERROR),
                message=f"Elasticsearch 관리도구 Indices Placement 처리 중 오류가 발생했습니다: {str(e)}",
                data=None,
            ).model_dump(),
        )


@router.get("/indices", response_model=CommonRes, status_code=200)
async def indices(
    request: Request,
    include_hidden_index: bool = Query(default=False, description="숨김 인덱스 포함 여부"),
    include_closed_index: bool = Query(default=False, description="닫힌 인덱스 포함 여부"),
) -> JSONResponse:
    try:
        es_client = get_elasticsearch_client(request.app)
        indices_service = IndicesService(es_client=es_client)

        result = await indices_service.indices(
            include_hidden_index=include_hidden_index,
            include_closed_index=include_closed_index,
        )

        return JSONResponse(
            status_code=HTTP_200_OK,
            headers={"Content-Type": "application/json"},
            content=CommonRes(data=result.model_dump(mode="json")).model_dump(),
        )
    except BizException as e:
        logger.error(f"Error in Indices List Check: {e}")
        return JSONResponse(
            status_code=e.status_code,
            content=CommonRes(
                code=str(e.status_code),
                message=e.message,
                data=None,
            ).model_dump(),
        )
    except Exception as e:
        logger.error(f"Error in Indices List Check: {e}")
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content=CommonRes(
                code=str(HTTP_500_INTERNAL_SERVER_ERROR),
                message=f"Elasticsearch 관리도구 Indices List 처리 중 오류가 발생했습니다: {str(e)}",
                data=None,
            ).model_dump(),
        )


@router.get("/indices/{index_name}", response_model=CommonRes, status_code=200)
async def index_detail(
    request: Request,
    index_name: str,
) -> JSONResponse:
    try:
        es_client = get_elasticsearch_client(request.app)
        indices_service = IndicesService(es_client=es_client)

        result = await indices_service.index_detail(index_name=index_name)

        return JSONResponse(
            status_code=HTTP_200_OK,
            headers={"Content-Type": "application/json"},
            content=CommonRes(data=result.model_dump(mode="json")).model_dump(),
        )
    except BizException as e:
        logger.error(f"Error in Index Detail Check: {e}")
        return JSONResponse(
            status_code=e.status_code,
            content=CommonRes(
                code=str(e.status_code),
                message=e.message,
                data=None,
            ).model_dump(),
        )
    except Exception as e:
        logger.error(f"Error in Index Detail Check: {e}")
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content=CommonRes(
                code=str(HTTP_500_INTERNAL_SERVER_ERROR),
                message=f"Elasticsearch 관리도구 Index Detail 처리 중 오류가 발생했습니다: {str(e)}",
                data=None,
            ).model_dump(),
        )