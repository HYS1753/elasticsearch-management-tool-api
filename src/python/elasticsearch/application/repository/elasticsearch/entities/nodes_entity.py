from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ClusterNodeEntity(BaseModel):
    name: str                           = Field(..., title="Node Name")
    transport_address: str              = Field(..., title="Node Transport Address")
    ip: str                             = Field(..., title="Node IP")
    roles: List[str]                    = Field(..., title="Node Roles")
    settings: Dict[str, Any]            = Field(..., title="Node Settings")

class ClusterNodesEntity(BaseModel):
    nodes: Dict[str, ClusterNodeEntity] = Field(..., title="Nodes Info")