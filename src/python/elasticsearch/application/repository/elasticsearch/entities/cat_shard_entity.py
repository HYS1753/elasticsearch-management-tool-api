from pydantic import BaseModel, Field
from typing import List, Any, Dict, Optional


class ShardEntity(BaseModel):
    id: str             = Field(..., title="Shard ID")
    index: str          = Field(..., title="Index name")
    shard: str          = Field(..., title="Shard number")
    prirep: str         = Field(..., title="Shard info(p: primary, r: replica)")
    state: str          = Field(..., title="Shard state(INITIALIZING, RELOCATING, STARTED, UNASSIGNED")
    node: str           = Field(..., title="Shard located node")
    store: str          = Field(..., title="Shard store size")
    docs: str           = Field(..., title="Shard docs size")
    ur: Optional[str]   = Field(None, title="Shard unassigend reason")
    ud: Optional[str]   = Field(None, title="Shard unassigend detail")

class ShardsEntity(BaseModel):
    shards: List[ShardEntity] = Field(..., title="Shards Info")