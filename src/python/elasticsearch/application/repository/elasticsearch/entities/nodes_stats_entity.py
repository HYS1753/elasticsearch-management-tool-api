from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict

class NodeStatEntity(BaseModel):
    indices: Dict[str, Any]             = Field(..., title="Node Indices Info")
    os: Dict[str, Any]                  = Field(..., title="Node OS info(CPU, Memory, etc)")
    jvm: Dict[str, Any]                 = Field(..., title="Node JVM info")
    thread_pool: Dict[str, Any]         = Field(..., title="Node Thread Pool info")
    fs: Dict[str, Any]                  = Field(..., title="Node FS(File System) info")
    indexing_pressure: Dict[str, Any]   = Field(..., title="Node Indexing Pressure info")

class NodesStatsEntity(BaseModel):
    nodes: Dict[str, NodeStatEntity]    = Field(..., title="Nodes Info")