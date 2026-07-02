from typing import Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class SuccessResponse(BaseModel, Generic[DataT]):
    success: bool = True
    data: DataT


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, object] = {}


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
