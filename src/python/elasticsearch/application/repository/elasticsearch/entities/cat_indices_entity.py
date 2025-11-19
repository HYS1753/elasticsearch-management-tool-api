from pydantic import BaseModel, Field
from typing import Optional, List


class IndexEntity(BaseModel):
    health: Optional[str] = Field(None, title="Index health (green, yellow, red)")
    status: Optional[str] = Field(None, title="Index status (open, close)")
    index: str = Field(..., title="Index name")
    uuid: str = Field(..., title="Index UUID")

    pri: Optional[str] = Field(None, title="Primary shard count")
    rep: Optional[str] = Field(None, title="Replica shard count")

    docs_count: Optional[str] = Field(None, alias="docs.count", title="Document count")
    docs_deleted: Optional[str] = Field(None, alias="docs.deleted", title="Deleted docs")

    store_size: Optional[str] = Field(None, alias="store.size", title="Total store size")
    pri_store_size: Optional[str] = Field(None, alias="pri.store.size", title="Primary store size")
    dataset_size: Optional[str] = Field(None, alias="dataset.size", title="Dataset size")


class IndicesEntity(BaseModel):
    indices: List[IndexEntity] = Field(..., title="Indices Info")