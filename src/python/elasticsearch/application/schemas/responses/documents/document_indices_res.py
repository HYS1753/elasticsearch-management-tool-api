from pydantic import BaseModel, Field


class DocumentIndexItem(BaseModel):
    index: str = Field(description="인덱스명")
    health: str | None = Field(default=None)
    status: str | None = Field(default=None)
    docs_count: str | None = Field(default=None)
    store_size: str | None = Field(default=None)


class DocumentIndicesRes(BaseModel):
    indices: list[DocumentIndexItem] = Field(default_factory=list)