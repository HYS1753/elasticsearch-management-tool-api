import logging
from pydantic import BaseModel, Field
from typing import List, Any

logger = logging.getLogger(__name__)

class IndicesPlacementRes(BaseModel):
    nodes: List[Any]                = Field(None, description="노드 정보 리스트")
    indices: List[Any]              = Field(None, description="인덱스 내 샤드 정보 리스트")
    has_unassigned_shards: bool     = Field(False, description="인덱스 내 unassigned shard 존재 여부")