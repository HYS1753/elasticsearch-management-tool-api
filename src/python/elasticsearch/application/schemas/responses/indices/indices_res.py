from typing import Optional

from pydantic import BaseModel, Field

class IndexInfoRes(BaseModel):
    health: str                      = Field(..., title="Index health (green, yellow, red)")
    status: str                      = Field(..., title="Index status (open/close)")
    index: str                       = Field(..., title="Index name")
    uuid: str                        = Field(..., title="Index UUID")
    pri: str                         = Field(..., title="Primary shard count")
    rep: str                         = Field(..., title="Replica shard count")
    docs_count: Optional[str]        = Field(None, title="Document count")
    docs_deleted: Optional[str]      = Field(None, title="Deleted docs")
    store_size: Optional[str]        = Field(None, title="Total store size")
    pri_store_size: Optional[str]    = Field(None, title="Primary store size")
    dataset_size: Optional[str]      = Field(None, title="Dataset size")

class IndicesRes(BaseModel):
    indices: list[IndexInfoRes]      = Field(..., title="Indices Info")