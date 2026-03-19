from typing import Any, Literal

from pydantic import BaseModel, Field


class IndexActionRes(BaseModel):
    index_name: str = Field(description="대상 인덱스명")
    action: Literal[
        "open",
        "close",
        "update_read_only",
        "refresh",
        "flush",
        "forcemerge",
        "delete",
    ] = Field(description="실행된 액션")
    acknowledged: bool = Field(description="Elasticsearch acknowledge 여부")
    message: str = Field(description="액션 결과 메시지")
    details: dict[str, Any] | None = Field(default=None, description="원본 응답")