from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict

class NodesSummaryInfoEntity(BaseModel):
    total: int                          = Field(..., title="Total Nodes Count")
    successful: int                     = Field(..., title="Successful Nodes Count")
    failed: int                         = Field(..., title="Failed Nodes Count")

class NodeInfoEntity(BaseModel):
    name: str                           = Field(..., title="Node Name")
    transport_address: str              = Field(..., title="Transport Address")
    host: str                           = Field(..., title="Node Host")
    ip: str                             = Field(..., title="Node IP")
    roles: List[str]                    = Field(..., title="Node Roles")
    indices: Dict[str, Any]             = Field(..., title="Node Indices Info")
    os: Dict[str, Any]                  = Field(..., title="Node OS info(CPU, Memory, etc)")
    jvm: Dict[str, Any]                 = Field(..., title="Node JVM info")
    gc: Dict[str, Any]                  = Field(..., title="Node GC info")
    thread_pool: Dict[str, Any]         = Field(..., title="Node Thread Pool info")
    fs: Dict[str, Any]                  = Field(..., title="Node FS(File System) info")
    indexing_pressure: Dict[str, Any]   = Field(..., title="Node Indexing Pressure info")

class NodesStatsEntity(BaseModel):
    _nodes: NodesSummaryInfoEntity      = Field(..., title="Nodes Stats")
    cluster_name: str                   = Field(..., title="Cluster Name")
    nodes: List[NodeInfoEntity]         = Field(..., title="Nodes Info")