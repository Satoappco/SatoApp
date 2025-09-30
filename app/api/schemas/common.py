"""
Common schemas used across the API
"""

from pydantic import BaseModel
from typing import Optional, Any


class BaseResponse(BaseModel):
    """Base response schema"""
    status: str
    message: Optional[str] = None
    timestamp: str


class ErrorResponse(BaseResponse):
    """Error response schema"""
    error: str
    code: Optional[str] = None


class SuccessResponse(BaseResponse):
    """Success response schema"""
    data: Optional[Any] = None
