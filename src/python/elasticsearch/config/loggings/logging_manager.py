from src.python.elasticsearch.config.settings.env_settings import settings
import logging.config
from pathlib import Path

# ✅ 로그 디렉터리 및 파일명 환경변수에서 가져오기
LOG_DIR = Path(settings.LOG_DIR)
LOG_FILE_NAME = settings.LOG_FILE_NAME
LOG_LEVEL = settings.LOG_LEVEL.upper()  # 🔥 대문자로 변환해서 사용

# ✅ 로그 디렉터리 생성 (없으면 자동 생성)
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE_PATH = LOG_DIR / LOG_FILE_NAME

# ✅ 전역 로깅 설정
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,  # ✅ 기존 로거 비활성화 방지
    "formatters": {
        "default": {
            "format": "%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "detailed": {
            "format": "%(asctime)s - [%(levelname)s] - %(name)s - %(filename)s:%(lineno)d - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": LOG_LEVEL
        },
        "file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "formatter": "detailed",
            "filename": str(LOG_FILE_PATH),
            "when": "midnight",
            "interval": 1,
            "backupCount": 7,
            "encoding": "utf-8",
            "level": LOG_LEVEL
        },
    },
    "root": {  # ✅ 전역적으로 root logger를 설정
        "level": LOG_LEVEL,
        "handlers": ["console", "file"],
    },
    "loggers": {
        "src": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "uvicorn": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "elasticsearch": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "elastic_transport": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
    }
}

# ✅ 전역적으로 로깅 설정 적용 (FastAPI 실행 전)
logging.config.dictConfig(LOGGING_CONFIG)

# ✅ 전역적으로 사용자 지정 로깅 레벨 설정
logging.getLogger("pymongo.topology").setLevel(logging.WARNING)
logging.getLogger("pymongo.connection").setLevel(logging.WARNING)
logging.getLogger("pymongo.command").setLevel(logging.WARNING)
logging.getLogger("pymongo.serverSelection").setLevel(logging.WARNING)

# ✅ 로깅 테스트 메시지
logger = logging.getLogger(__name__)
logger.info("🚀 Item Search Agent Logging is configured successfully!")
