# Logging Import
import logging
import  src.python.elasticsearch.config.loggings.logging_manager

import uvicorn, contextlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHttpException
from fastapi.exceptions import RequestValidationError

from src.python.elasticsearch.application.endpoints.indices_endpoint import indices_endpoint
from src.python.elasticsearch.application.endpoints.search_explain_endpoint import search_explain_endpoint
from src.python.elasticsearch.application.endpoints.documents_endpoint import documents_endpoint
from src.python.elasticsearch.config.connections.elasticsearch_connection_manager import EsConnectionManager, \
    init_elasticsearch_connection, close_elasticsearch_connection
from src.python.elasticsearch.config.settings.env_settings import settings
from src.python.elasticsearch.config.exceptions.exception_handlers import (
    http_exception_handler,
    validation_exception_handler,
    internal_server_error_handler,
    biz_exception_handler
)
from src.python.elasticsearch.config.exceptions.biz_exceptions import BizException
from src.python.elasticsearch.application.endpoints.cluster_endpoint import cluster_endpoint

logger = logging.getLogger(__name__)

# LifeSpan 설정
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"=========================================================")
    logger.info(f"Environment: {settings.ENVIRONMENT.value}")
    logger.info(f"Version: {settings.APPLICATION_VERSION}")
    logger.info(f"applicaiton name: {settings.APPLICATION_NAME}")
    logger.info(f"application port: {settings.APPLICATION_PORT}")
    logger.info(f"==========================================================")

    try:
        # Connection 초기화
        init_elasticsearch_connection(app)

        # Application start
        yield

    except Exception as e:
        logger.error(f"애플리케이션 수명 주기 오류: {e}")
        raise e
    finally:
        logger.info(f"=========================================================")
        logger.info(f"{settings.APPLICATION_NAME} Application shutdown start")
        await close_elasticsearch_connection(app=app)
        logger.info(f"{settings.APPLICATION_NAME} Application shutdown complete")
        logger.info(f"=========================================================")

# FastAPI 설정 (운영 분기)
if settings.ENVIRONMENT.is_prod():
    app = FastAPI(title="Elasticsearch Management Tool API", version="1.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https:\/\/(.*\.)?elasticsearch\.(co\.kr|biz)$",  # Allows the example origin
        allow_credentials=True,
        allow_methods=["*"],  # Allows all methods
        allow_headers=["*"],  # Allows all headers
    )
else:
    app = FastAPI(title="Elasticsearch Management Tool API", version="1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allows the example origin
        allow_credentials=True,
        allow_methods=["*"],  # Allows all methods
        allow_headers=["*"],  # Allows all headers
    )

# Exception 등록
app.add_exception_handler(StarletteHttpException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, internal_server_error_handler)
app.add_exception_handler(BizException, biz_exception_handler)

app.include_router(cluster_endpoint, prefix="/app/cluster", tags=["Elasticsearch Cluster API"])
app.include_router(indices_endpoint, prefix="/app/indices", tags=["Elasticsearch Indices API"])
app.include_router(search_explain_endpoint, prefix="/app/search/explain", tags=["Elasticsearch Search Explain API"])
app.include_router(documents_endpoint, prefix="/app/documents", tags=["documents"])

if __name__ == "__main__":
    try:
        logger.info(f"🚀 Starting Elasticsearch Management Tool API server on port {settings.APPLICATION_PORT}")
        uvicorn.run(
            "src.python.main:app", # reload 사용을 위해서는 위치를 str로 지정 필요, reload 시 새로운 프로세스를 spawn하기 때문에 객체로 넘길 시 uvicorn 이 재시작 할 경로를 못찾음.
            host="0.0.0.0",
            port=settings.APPLICATION_PORT,
            reload=(settings.ENVIRONMENT.is_dev()),
            reload_dirs=["src"],
            workers=settings.APPLICATION_WORKERS,
            log_level=settings.LOG_LEVEL.lower(),
            access_log=settings.APPLICATION_ACCESS_LOG
        )
    except Exception as e:
        print(f"서버 시작 실패: {e}")
        exit(1)