from pydantic import BaseModel, Field
from typing import Any, Optional

'''
공통 response message
'''
class CommonRes(BaseModel):
    code: str = Field("200", title="코드", description="결과 코드")
    message: str = Field("정상적으로 처리 되었습니다.", title="메시지", description="결과 메시지")
    data: Optional[Any] = Field(None, title="데이터", description="결과 데이터")
