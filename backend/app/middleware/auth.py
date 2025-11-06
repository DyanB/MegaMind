from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from app.services.auth_service import AuthService
from app.models.auth import UserResponse

security = HTTPBearer(auto_error=False)


async def get_current_user_from_token(request: Request) -> Optional[UserResponse]:
    """
    Extract user from JWT token in Authorization header.
    Returns None if no token or invalid token (for optional auth).
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.replace("Bearer ", "")
    
    try:
        auth_service = AuthService()
        user = auth_service.verify_token(token)
        return user
    except Exception:
        return None


async def require_auth(request: Request) -> UserResponse:
    """
    Require authentication. Raises 401 if not authenticated.
    Use this for endpoints that MUST have a logged-in user.
    """
    user = await get_current_user_from_token(request)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user
