from pydantic import BaseModel
from typing import List, Generic, TypeVar

T = TypeVar('T')

class DictionaryListRes(BaseModel, Generic[T]):
    total_count: int
    items: List[T]
