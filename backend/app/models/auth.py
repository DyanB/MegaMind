"""
User authentication and management models
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """User roles for access control"""
    FREE = "free"
    PRO = "pro"
    ADMIN = "admin"


class UserBase(BaseModel):
    """Base user model"""
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.FREE


class UserCreate(BaseModel):
    """User registration model"""
    email: EmailStr
    full_name: str
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    """User login model"""
    email: EmailStr
    password: str


class UserInDB(UserBase):
    """User model as stored in database"""
    id: str = Field(alias="_id")
    hashed_password: str
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    api_usage: dict = {}  # Track API usage per month
    
    class Config:
        populate_by_name = True


class UserResponse(UserBase):
    """User model for API responses (no sensitive data)"""
    id: str
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    """Token payload data"""
    user_id: Optional[str] = None
    email: Optional[str] = None
