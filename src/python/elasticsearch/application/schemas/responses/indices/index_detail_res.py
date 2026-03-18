from typing import List, Optional

from pydantic import BaseModel, Field


class IndexDetailSummaryRes(BaseModel):
    index: str = Field(..., title="Index name")
    uuid: str = Field(..., title="Index UUID")
    health: str = Field(..., title="Index health")
    status: str = Field(..., title="Index status")
    pri: str = Field(..., title="Primary shard count")
    rep: str = Field(..., title="Replica shard count")
    docs_count: Optional[str] = Field(None, title="Document count")
    docs_deleted: Optional[str] = Field(None, title="Deleted docs count")
    store_size: Optional[str] = Field(None, title="Store size")
    pri_store_size: Optional[str] = Field(None, title="Primary store size")
    dataset_size: Optional[str] = Field(None, title="Dataset size")


class IndexAliasRes(BaseModel):
    name: str = Field(..., title="Alias name")
    is_write_index: bool = Field(False, title="Is write index")
    filter: Optional[str] = Field(None, title="Alias filter")
    routing_index: Optional[str] = Field(None, title="Index routing")
    routing_search: Optional[str] = Field(None, title="Search routing")


class IndexSettingRes(BaseModel):
    key: str = Field(..., title="Setting key")
    value: str = Field(..., title="Setting value")


class IndexMappingFieldRes(BaseModel):
    name: str = Field(..., title="Field name")
    type: str = Field(..., title="Field type")
    children: List["IndexMappingFieldRes"] = Field(default_factory=list, title="Child fields")


class IndexStatsRes(BaseModel):
    docs_count: int = Field(0, title="Document count")
    docs_deleted: int = Field(0, title="Deleted document count")
    store_size_in_bytes: int = Field(0, title="Store size in bytes")
    primary_store_size_in_bytes: int = Field(0, title="Primary store size in bytes")
    search_query_total: int = Field(0, title="Search query total")
    indexing_index_total: int = Field(0, title="Indexing total")


class IndexDetailRes(BaseModel):
    summary: IndexDetailSummaryRes = Field(..., title="Index summary")
    aliases: List[IndexAliasRes] = Field(default_factory=list, title="Index aliases")
    settings: List[IndexSettingRes] = Field(default_factory=list, title="Flat settings")
    mappings: List[IndexMappingFieldRes] = Field(default_factory=list, title="Mappings tree")
    stats: IndexStatsRes = Field(..., title="Index stats")


IndexMappingFieldRes.model_rebuild()