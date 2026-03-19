import logging

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR

from src.python.elasticsearch.application.schemas.requests.documents.document_search_req import (
    DocumentSearchReq,
)
from src.python.elasticsearch.application.schemas.responses.common.common_res import CommonRes
from src.python.elasticsearch.application.services.api.documents_service import (
    DocumentsService,
)
from src.python.elasticsearch.config.connections.elasticsearch_connection_manager import (
    get_elasticsearch_client,
)
from src.python.elasticsearch.config.exceptions.biz_exceptions import BizException

logger = logging.getLogger(__name__)

router = APIRouter()
documents_endpoint = router


@router.get("/indices", response_model=CommonRes, status_code=200)
async def document_indices(request: Request) -> JSONResponse:
    try:
        es_client = get_elasticsearch_client(request.app)
        documents_service = DocumentsService(es_client=es_client)
        result = await documents_service.get_document_indices()

        return JSONResponse(
            status_code=HTTP_200_OK,
            headers={"Content-Type": "application/json"},
            content=CommonRes(data=result.model_dump(mode="json")).model_dump(),
        )
    except BizException as e:
        logger.error(f"Error in Document Indices: {e}")
        return JSONResponse(
            status_code=e.status_code,
            content=CommonRes(
                code=str(e.status_code),
                message=str(e),
                data=None,
            ).model_dump(),
        )
    except Exception as e:
        logger.error(f"Error in Document Indices: {e}")
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content=CommonRes(
                code=str(HTTP_500_INTERNAL_SERVER_ERROR),
                message=f"Elasticsearch 관리도구 Document Indices 처리 중 오류가 발생했습니다: {str(e)}",
                data=None,
            ).model_dump(),
        )


@router.post("/search", response_model=CommonRes, status_code=200)
async def search_documents(
    request: Request,
    search_req: DocumentSearchReq,
) -> JSONResponse:
    try:
        es_client = get_elasticsearch_client(request.app)
        documents_service = DocumentsService(es_client=es_client)
        result = await documents_service.search_documents(search_req=search_req)

        return JSONResponse(
            status_code=HTTP_200_OK,
            headers={"Content-Type": "application/json"},
            content=CommonRes(data=result.model_dump(mode="json", by_alias=True)).model_dump(),
        )
    except BizException as e:
        logger.error(f"Error in Document Search: {e}")
        return JSONResponse(
            status_code=e.status_code,
            content=CommonRes(
                code=str(e.status_code),
                message=str(e),
                data=None,
            ).model_dump(),
        )
    except Exception as e:
        logger.error(f"Error in Document Search: {e}")
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content=CommonRes(
                code=str(HTTP_500_INTERNAL_SERVER_ERROR),
                message=f"Elasticsearch 관리도구 Document Search 처리 중 오류가 발생했습니다: {str(e)}",
                data=None,
            ).model_dump(),
        )