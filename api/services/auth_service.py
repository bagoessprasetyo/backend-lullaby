# api/services/auth_service.py
import time
from typing import Dict, Optional, Tuple
from fastapi import Request, HTTPException, status
from jose import jwt, JWTError
from pydantic import BaseModel

from config import settings
from utils.logger import get_logger
from db.repositories.user_repository import UserRepository

logger = get_logger("auth_service")

class TokenData(BaseModel):
    sub: str
    exp: Optional[int] = None
    email: Optional[str] = None


async def decode_jwt(token: str) -> Dict:
    """Decode and validate JWT token"""
    try:
        # This is a simplified example - in production you'd validate with proper key
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=["HS256"]
        )
        
        # Check if token has expired
        if "exp" in payload and payload["exp"] < time.time():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Token has expired"
            )
            
        return payload
    except JWTError as e:
        logger.error(f"JWT error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid authentication credentials"
        )
    except Exception as e:
        logger.error(f"Token decode error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Authentication error"
        )


async def get_current_user(request: Request) -> Tuple[str, dict]:
    """Extract and validate user from request"""
    # Get token from authorization header
    authorization = request.headers.get("Authorization")
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Not authenticated"
        )
        
    try:
        # Extract token
        if " " in authorization:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, 
                    detail="Invalid authentication scheme"
                )
        else:
            token = authorization
            
        # Decode token
        payload = await decode_jwt(token)
        
        # Extract user ID
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid token payload"
            )
            
        # Get user from database
        user = await UserRepository.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )
            
        return user_id, user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Authentication error"
        )


async def require_subscription(user_id: str, required_tier: str = "premium") -> Dict:
    """Check if user has required subscription tier"""
    features = await UserRepository.check_subscription_features(user_id)
    
    if not features["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=features.get("reason", "Failed to check subscription")
        )
        
    subscription_tier = features["subscription_tier"]
    
    if subscription_tier != required_tier and subscription_tier != "family":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"This feature requires a {required_tier} subscription"
        )
        
    return features


async def mock_auth_handler(token: str) -> str:
    """
    Mock authentication for development and testing
    In production, replace with proper JWT verification
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Not authenticated"
        )
        
    # For development, simply use the token as the user ID
    # In production, decode and verify the JWT properly
    return token