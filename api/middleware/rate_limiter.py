# api/middleware/rate_limiter.py
import time
import asyncio
from typing import Dict, Tuple, Optional, Callable, List
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from config import settings
from utils.logger import get_logger
from db.repositories.user_repository import UserRepository

logger = get_logger("rate_limiter")

# In-memory rate limit store
# In production, use Redis or another distributed store
rate_limit_store: Dict[str, Dict[str, int]] = {}

# Rate limit rules based on subscription tier
RATE_LIMIT_RULES = {
    "free": {
        "story_generation": {"limit": 5, "window": 3600},  # 5 per hour
        "get_stories": {"limit": 100, "window": 3600},     # 100 per hour
        "general": {"limit": 200, "window": 3600}          # 200 per hour
    },
    "premium": {
        "story_generation": {"limit": 20, "window": 3600}, # 20 per hour
        "get_stories": {"limit": 500, "window": 3600},     # 500 per hour
        "general": {"limit": 1000, "window": 3600}         # 1000 per hour
    },
    "family": {
        "story_generation": {"limit": 30, "window": 3600}, # 30 per hour
        "get_stories": {"limit": 1000, "window": 3600},    # 1000 per hour
        "general": {"limit": 2000, "window": 3600}         # 2000 per hour
    }
}

# Endpoint to rate limit rule mapping
ENDPOINT_RULES = {
    "/api/stories/generate": "story_generation",
    "/api/stories/": "get_stories"
}


class RateLimiter(BaseHTTPMiddleware):
    """Rate limiting middleware for API endpoints"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and apply rate limiting"""
        # Skip rate limiting for some paths
        if request.url.path in ["/", "/api/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
            
        # Get client IP address
        client_ip = request.client.host if request.client else "unknown"
        
        # Try to get user ID from authorization header
        user_id = "anonymous"
        
        if "authorization" in request.headers:
            auth = request.headers["authorization"]
            if " " in auth:
                scheme, token = auth.split()
                if scheme.lower() == "bearer":
                    # In production, properly decode the JWT
                    # For now, just use the token as user ID
                    user_id = token
            else:
                user_id = auth
                
        # Get rate limit rule for this endpoint
        rule_key = "general"
        
        for endpoint, rule in ENDPOINT_RULES.items():
            if request.url.path.startswith(endpoint):
                rule_key = rule
                break
                
        # Get user's subscription tier
        subscription_tier = "free"
        
        try:
            if user_id != "anonymous":
                user = await UserRepository.get_user_by_id(user_id)
                if user:
                    subscription_tier = user.get("subscription_tier", "free")
        except Exception as e:
            logger.error(f"Error getting user subscription tier: {str(e)}")
        
        # Get rate limit for this tier and rule
        rate_limit = RATE_LIMIT_RULES[subscription_tier][rule_key]["limit"]
        window = RATE_LIMIT_RULES[subscription_tier][rule_key]["window"]
        
        # Create unique key for this user/endpoint
        rate_key = f"{user_id}:{rule_key}"
        
        # Check rate limit
        current_time = int(time.time())
        
        # Initialize if not exists
        if rate_key not in rate_limit_store:
            rate_limit_store[rate_key] = {"count": 0, "reset": current_time + window}
            
        # Clean up expired entries
        if rate_limit_store[rate_key]["reset"] <= current_time:
            rate_limit_store[rate_key] = {"count": 0, "reset": current_time + window}
            
        # Check if limit exceeded
        if rate_limit_store[rate_key]["count"] >= rate_limit:
            retry_after = rate_limit_store[rate_key]["reset"] - current_time
            
            # Add rate limit headers
            headers = {
                "X-RateLimit-Limit": str(rate_limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(rate_limit_store[rate_key]["reset"]),
                "Retry-After": str(retry_after)
            }
            
            # Log rate limit exceeded
            logger.warning(f"Rate limit exceeded for {user_id} ({client_ip}) on {rule_key}")
            
            # Return rate limit exceeded response
            return Response(
                content=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers=headers
            )
            
        # Increment count
        rate_limit_store[rate_key]["count"] += 1
        
        # Add rate limit headers to response
        response = await call_next(request)
        
        response.headers["X-RateLimit-Limit"] = str(rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(rate_limit - rate_limit_store[rate_key]["count"])
        response.headers["X-RateLimit-Reset"] = str(rate_limit_store[rate_key]["reset"])
        
        return response

    # Function to periodically clean up rate limit store
    async def cleanup_rate_limits():
        """Clean up expired rate limit entries"""
        while True:
            try:
                current_time = int(time.time())
                
                # Find and remove expired entries
                expired_keys = []
                
                for key, data in rate_limit_store.items():
                    if data["reset"] <= current_time:
                        expired_keys.append(key)
                        
                # Remove expired keys
                for key in expired_keys:
                    del rate_limit_store[key]
                    
                # Log cleanup
                if expired_keys:
                    logger.debug(f"Cleaned up {len(expired_keys)} expired rate limit entries")
                    
            except Exception as e:
                logger.error(f"Error cleaning up rate limits: {str(e)}")
                
            # Sleep for 5 minutes
            await asyncio.sleep(300)