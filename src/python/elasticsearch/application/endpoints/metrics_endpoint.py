import logging

from typing import Optional
from fastapi import APIRouter, Query, Depends, Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR, HTTP_200_OK

from src.python.elasticsearch.application.schemas.responses.common.common_res import CommonRes
from src.python.elasticsearch.application.services.api.metrics_service import MetricsService
from src.python.elasticsearch.config.connections.prometheus_connection_manager import get_prometheus_session
from src.python.elasticsearch.application.endpoints.auth_endpoint import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()
metrics_endpoint = router


@router.get("/cluster-overview", response_model=CommonRes, status_code=200)
async def cluster_overview(
    request: Request,
    env: Optional[str] = Query(None, description="환경 필터 (dev/prod). 미지정 시 APPLICATION_ACTIVE_PROFILE 사용"),
    _=Depends(get_current_user),
) -> JSONResponse:
    """클러스터 헬스 요약 (instant)"""
    try:
        session = get_prometheus_session(request.app)
        service = MetricsService(session=session)
        result = await service.get_cluster_overview(env=env)
        return JSONResponse(
            status_code=HTTP_200_OK,
            content=CommonRes(data=result.model_dump(mode="json")).model_dump(),
        )
    except Exception as e:
        logger.error(f"Error in cluster overview metrics: {e}")
        return JSONResponse(
            status_code=500,
            content=CommonRes(
                code=str(HTTP_500_INTERNAL_SERVER_ERROR),
                message=f"Prometheus 클러스터 메트릭 조회 중 오류가 발생했습니다: {str(e)}",
                data=None,
            ).model_dump(),
        )


@router.get("/node-resources", response_model=CommonRes, status_code=200)
async def node_resources(
    request: Request,
    time_range: str = Query("1h", description="조회 범위 (15m/1h/6h/24h/7d)"),
    start: Optional[str] = Query(None, description="조회 시작 범위 타임스탬프 또는 ISO 포맷"),
    end: Optional[str] = Query(None, description="조회 종료 범위 타임스탬프 또는 ISO 포맷"),
    step: Optional[str] = Query(None, description="데이터 간격 (예: 30s, 60s). 미지정 시 자동 계산"),
    env: Optional[str] = Query(None),
    _=Depends(get_current_user),
) -> JSONResponse:
    """노드 리소스 시계열 (CPU/Memory/JVM/GC)"""
    try:
        session = get_prometheus_session(request.app)
        service = MetricsService(session=session)
        result = await service.get_node_resources(env=env, time_range=time_range, start=start, end=end, step=step)
        return JSONResponse(
            status_code=HTTP_200_OK,
            content=CommonRes(data=result.model_dump(mode="json")).model_dump(),
        )
    except Exception as e:
        logger.error(f"Error in node resources metrics: {e}")
        return JSONResponse(
            status_code=500,
            content=CommonRes(
                code=str(HTTP_500_INTERNAL_SERVER_ERROR),
                message=f"Prometheus 노드 리소스 메트릭 조회 중 오류가 발생했습니다: {str(e)}",
                data=None,
            ).model_dump(),
        )


@router.get("/search-performance", response_model=CommonRes, status_code=200)
async def search_performance(
    request: Request,
    time_range: str = Query("1h"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    step: Optional[str] = Query(None),
    env: Optional[str] = Query(None),
    _=Depends(get_current_user),
) -> JSONResponse:
    """검색 성능 시계열 (Query Rate/Latency, Fetch Rate/Latency)"""
    try:
        session = get_prometheus_session(request.app)
        service = MetricsService(session=session)
        result = await service.get_search_performance(env=env, time_range=time_range, start=start, end=end, step=step)
        return JSONResponse(
            status_code=HTTP_200_OK,
            content=CommonRes(data=result.model_dump(mode="json")).model_dump(),
        )
    except Exception as e:
        logger.error(f"Error in search performance metrics: {e}")
        return JSONResponse(
            status_code=500,
            content=CommonRes(
                code=str(HTTP_500_INTERNAL_SERVER_ERROR),
                message=f"Prometheus 검색 성능 메트릭 조회 중 오류가 발생했습니다: {str(e)}",
                data=None,
            ).model_dump(),
        )


@router.get("/indexing-performance", response_model=CommonRes, status_code=200)
async def indexing_performance(
    request: Request,
    time_range: str = Query("1h"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    step: Optional[str] = Query(None),
    env: Optional[str] = Query(None),
    _=Depends(get_current_user),
) -> JSONResponse:
    """인덱싱 성능 시계열 (Index Rate/Latency, Delete Rate)"""
    try:
        session = get_prometheus_session(request.app)
        service = MetricsService(session=session)
        result = await service.get_indexing_performance(env=env, time_range=time_range, start=start, end=end, step=step)
        return JSONResponse(
            status_code=HTTP_200_OK,
            content=CommonRes(data=result.model_dump(mode="json")).model_dump(),
        )
    except Exception as e:
        logger.error(f"Error in indexing performance metrics: {e}")
        return JSONResponse(
            status_code=500,
            content=CommonRes(
                code=str(HTTP_500_INTERNAL_SERVER_ERROR),
                message=f"Prometheus 인덱싱 성능 메트릭 조회 중 오류가 발생했습니다: {str(e)}",
                data=None,
            ).model_dump(),
        )


@router.get("/cache-threadpool", response_model=CommonRes, status_code=200)
async def cache_threadpool(
    request: Request,
    time_range: str = Query("1h"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    step: Optional[str] = Query(None),
    env: Optional[str] = Query(None),
    _=Depends(get_current_user),
) -> JSONResponse:
    """캐시 및 스레드풀 메트릭 시계열"""
    try:
        session = get_prometheus_session(request.app)
        service = MetricsService(session=session)
        result = await service.get_cache_threadpool(env=env, time_range=time_range, start=start, end=end, step=step)
        return JSONResponse(
            status_code=HTTP_200_OK,
            content=CommonRes(data=result.model_dump(mode="json")).model_dump(),
        )
    except Exception as e:
        logger.error(f"Error in cache/threadpool metrics: {e}")
        return JSONResponse(
            status_code=500,
            content=CommonRes(
                code=str(HTTP_500_INTERNAL_SERVER_ERROR),
                message=f"Prometheus 캐시/스레드풀 메트릭 조회 중 오류가 발생했습니다: {str(e)}",
                data=None,
            ).model_dump(),
        )


@router.get("/storage-overview", response_model=CommonRes, status_code=200)
async def storage_overview(
    request: Request,
    env: Optional[str] = Query(None),
    _=Depends(get_current_user),
) -> JSONResponse:
    """노드별 스토리지 사용률 (instant)"""
    try:
        session = get_prometheus_session(request.app)
        service = MetricsService(session=session)
        result = await service.get_storage_overview(env=env)
        return JSONResponse(
            status_code=HTTP_200_OK,
            content=CommonRes(data=result.model_dump(mode="json")).model_dump(),
        )
    except Exception as e:
        logger.error(f"Error in storage overview metrics: {e}")
        return JSONResponse(
            status_code=500,
            content=CommonRes(
                code=str(HTTP_500_INTERNAL_SERVER_ERROR),
                message=f"Prometheus 스토리지 메트릭 조회 중 오류가 발생했습니다: {str(e)}",
                data=None,
            ).model_dump(),
        )
