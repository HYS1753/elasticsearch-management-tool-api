from fastapi import HTTPException
import logging

class BizException(HTTPException):
    def __init__(self, status_code: int, message: str = "Runtime Exception"):
        super().__init__(status_code=status_code, detail=message)
        logging.error(message)