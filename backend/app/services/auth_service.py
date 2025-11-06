"""
JWT Authentication Service
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from app.models.auth import UserCreate, UserInDB, UserResponse, TokenData
from app.database import MongoDB, COLLECTIONS
import uuid
import os

# Security configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


class AuthService:
    """Handle user authentication and JWT tokens"""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        # Truncate password to 72 bytes for bcrypt
        plain_password = plain_password[:72]
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password"""
        # Truncate password to 72 bytes for bcrypt compatibility
        password = password[:72]
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    async def verify_token(token: str) -> Optional[TokenData]:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            email: str = payload.get("email")
            
            if user_id is None:
                return None
            
            return TokenData(user_id=user_id, email=email)
        except JWTError:
            return None
    
    @staticmethod
    async def create_user(user_data: UserCreate) -> UserResponse:
        """Create a new user"""
        users_collection = MongoDB.get_collection(COLLECTIONS["users"])
        
        # Check if user already exists
        existing_user = await users_collection.find_one({"email": user_data.email})
        if existing_user:
            raise ValueError("User with this email already exists")
        
        # Create user document
        user_id = str(uuid.uuid4())
        user_doc = {
            "_id": user_id,
            "email": user_data.email,
            "full_name": user_data.full_name,
            "hashed_password": AuthService.get_password_hash(user_data.password),
            "role": "free",
            "created_at": datetime.utcnow(),
            "last_login": None,
            "is_active": True,
            "api_usage": {}
        }
        
        await users_collection.insert_one(user_doc)
        
        return UserResponse(
            id=user_id,
            email=user_data.email,
            full_name=user_data.full_name,
            role="free",
            created_at=user_doc["created_at"],
            last_login=None,
            is_active=True
        )
    
    @staticmethod
    async def authenticate_user(email: str, password: str) -> Optional[UserInDB]:
        """Authenticate a user by email and password"""
        users_collection = MongoDB.get_collection(COLLECTIONS["users"])
        
        user = await users_collection.find_one({"email": email})
        if not user:
            return None
        
        if not AuthService.verify_password(password, user["hashed_password"]):
            return None
        
        # Update last login
        await users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"last_login": datetime.utcnow()}}
        )
        
        return UserInDB(**user)
    
    @staticmethod
    async def get_user_by_id(user_id: str) -> Optional[UserResponse]:
        """Get user by ID"""
        users_collection = MongoDB.get_collection(COLLECTIONS["users"])
        
        user = await users_collection.find_one({"_id": user_id})
        if not user:
            return None
        
        return UserResponse(
            id=user["_id"],
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            created_at=user["created_at"],
            last_login=user.get("last_login"),
            is_active=user["is_active"]
        )
