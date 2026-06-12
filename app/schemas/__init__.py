# -*- coding: utf-8 -*-
"""
数据模式包
"""

from .auth import *
from .user import *
from .api_key import *

__all__ = [
    # Auth schemas
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserResponse",
    # User schemas
    "UserProfile",
    "UpdateProfileRequest",
    "ChangePasswordRequest",
    # API Key schemas
    "CreateApiKeyRequest",
    "UpdateApiKeyRequest",
    "ApiKeyResponse",
]
