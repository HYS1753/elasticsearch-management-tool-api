import logging
from pydantic import BaseModel, Field
from typing import Optional, List

logger = logging.getLogger(__name__)

class ClusterNodeRes(BaseModel):
    is_master_node: bool                    = Field(..., title="마스터 노드 여부")
    name: str                               = Field(..., title="노드 명")
    id: str                                 = Field(..., title="노드 ID")
    host: str                               = Field(..., title="노드 Host IP/Port")
    transport: str                          = Field(..., title="노드 Transport IP/Port")
    roles: List[str]                        = Field(..., title="노드 Roles 리스트")

class ClusterNodesRes(BaseModel):
    nodes: Optional[List[ClusterNodeRes]]   = Field([], description="클러스터 노드 기본 정보")