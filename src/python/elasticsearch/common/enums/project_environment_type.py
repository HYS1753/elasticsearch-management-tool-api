import logging
from enum import Enum

logger = logging.getLogger(__name__)

class ProjectEnvironmentType(str, Enum):
    DEVELOPMENT = "dev"
    STAGING = "stg"
    PRODUCTION = "prod"

    @classmethod
    def from_value(cls, value: str, default: "ProjectEnvironmentType" = None) -> "ProjectEnvironmentType":
        """문자열 값을 해당 Enum 멤버로 변환"""
        value = value.lower()

        if default is None:
            default = cls.DEVELOPMENT
        try:
            return cls(value)
        except ValueError:
            return default
        except Exception as e:
            logger.error(f"Error in ProjectEnvironmentType.from_value: {e}, setting default: {default.value}")
            return default

    def is_dev(self) -> bool:
        return self == ProjectEnvironmentType.DEVELOPMENT

    def is_stg(self) -> bool:
        return self == ProjectEnvironmentType.STAGING

    def is_prod(self) -> bool:
        return self == ProjectEnvironmentType.PRODUCTION