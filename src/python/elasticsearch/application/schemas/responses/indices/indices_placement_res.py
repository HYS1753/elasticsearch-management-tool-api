import logging
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class NodeViewRes(BaseModel):
    id: str             = Field(..., title="Node ID")
    name: str           = Field(..., title="Node Name")
    host: str           = Field(..., title="Node Host IP/Port")
    roles: List[str]    = Field(..., title="Node Roeles")
    is_master: bool     = Field(..., title="Node Master Eligible")

class ShardPlacementRes(BaseModel):
    shard: str                  = Field(..., title="Shard number")
    prirep: str                 = Field(..., title="p: primary, r: replica")
    state: str                  = Field(..., title="Shard state")
    node_id: Optional[str]      = Field(..., title="Node ID")
    node_name: Optional[str]    = Field(..., title="Node name")
    store: Optional[str]        = Field(..., title="Store size")
    docs: Optional[str]         = Field(..., title="Docs count")


class IndexPlacementRes(BaseModel):
    index: str          = Field(..., title="Index name")
    status: str         = Field(..., title="Index status(open/close)")
    shards_by_node: Dict[str, List[ShardPlacementRes]]  = Field(..., title="Shards by node")
    unassigned: List[ShardPlacementRes]                 = Field(..., title="Unassigned shards")


class IndicesPlacementRes(BaseModel):
    nodes: List[NodeViewRes]            = Field(..., title="Nodes")
    indices: List[IndexPlacementRes]    = Field(..., title="Indices placement")
    has_unassigned_shards: bool         = Field(..., title="Whether any unassigned shards exist")