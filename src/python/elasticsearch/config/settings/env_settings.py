import os
from pydantic_settings import BaseSettings

from src.python.elasticsearch.common.enums.project_environment_type import ProjectEnvironmentType


class Settings(BaseSettings):
    """Master Agent 환경 설정"""

    # === Application 설정 ===
    APPLICATION_ACTIVE_PROFILE: str = "dev"
    APPLICATION_NAME: str = "elasticsearch-management-tool-api"
    APPLICATION_PORT: int = 8000
    APPLICATION_VERSION: str = "1.0.0"
    APPLICATION_WORKERS: int = 1
    APPLICATION_ACCESS_LOG: bool = False

    # === 로깅 설정 ===
    LOG_LEVEL: str = "DEBUG"
    LOG_DIR: str = "logs"
    LOG_FILE_NAME: str = "app.log"

    # Elasticsearch
    ES_HOST: str = "https://localhost:9200"
    ES_API_KEY: str = ""
    ES_USER_ID: str = ""
    ES_USER_PW: str = ""
    ES_VERIFY_CERTS: bool = False
    ES_CERTS: str = "src/resources/es_certs/certificate.crt"
    ES_MAX_CONNECTION: int = 100
    ES_TIMEOUT: int = 30

    class Config:
        env_file = "src/resources/.env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # .env 파일의 추가 필드들을 무시

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._set_environ_vars()

    def _set_environ_vars(self):
        """환경 변수 설정"""
        # ex. os.environ["ENV_VARIABLE"] = str(self.ENV_VARIABLE)
        pass

    # 호환성을 위한 별칭
    @property
    def ENVIRONMENT(self) -> ProjectEnvironmentType:
        return ProjectEnvironmentType(self.APPLICATION_ACTIVE_PROFILE)

    @property
    def GET_ES_HOST(self) -> list[str]:
        """
        문자열 형태의 Elasticsearch 호스트 목록을 파싱하여 리스트로 반환합니다.

        예:
            "http://es1:9200,http://es2:9200"
            -> ["http://es1:9200", "http://es2:9200"]

            "http://localhost:9200"
            -> ["http://localhost:9200"]
        """
        hosts_str: str = self.ES_HOST
        if not hosts_str:
            return []

        # 쉼표 기준으로 분리 + 양쪽 공백 제거 + 빈 값 제거
        hosts = [h.strip() for h in hosts_str.split(",") if h.strip()]
        return hosts

# 환경 변수 인스턴스 생성
settings = Settings()
