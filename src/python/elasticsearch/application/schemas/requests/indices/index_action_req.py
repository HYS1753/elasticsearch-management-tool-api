from typing import Literal

from pydantic import BaseModel, Field


class IndexActionReq(BaseModel):
    action: Literal[
        "open",
        "close",
        "update_read_only",
        "refresh",
        "flush",
        "forcemerge",
        "delete",
    ] = Field(description="실행할 인덱스 액션")

    read_only: bool | None = Field(
        default=None,
        description="update_read_only 액션일 때 사용할 값",
    )

    max_num_segments: int | None = Field(
        default=None,
        ge=1,
        description="forcemerge 액션일 때 사용할 max_num_segments",
    )