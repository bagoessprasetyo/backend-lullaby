# api/middleware/error_handler.py
import traceback
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Message

from utils.logger import get_logger

logger = get_logger("error_handler")


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware for consistent error handling across the API"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """Process the request and handle any exceptions"""
        try:
            # Process the request
            response = await call_next(request)
            return response
            
        except Exception as e:
            # Log the exception
            logger.error(f"Unhandled exception: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Return a consistent error response
            return self.create_error_response(e)
    
    def create_error_response(self, exception: Exception) -> JSONResponse:
        """Create a standardized error response"""
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_type = "Internal Server Error"
        
        # Extract status code and error type from exception if available
        if hasattr(exception, "status_code"):
            status_code = exception.status_code
            
        if hasattr(exception, "detail"):
            error_detail = exception.detail
        else:
            error_detail = str(exception)
        
        # Map status code to error type
        if status_code == status.HTTP_400_BAD_REQUEST:
            error_type = "Bad Request"
        elif status_code == status.HTTP_401_UNAUTHORIZED:
            error_type = "Unauthorized"
        elif status_code == status.HTTP_403_FORBIDDEN:
            error_type = "Forbidden"
        elif status_code == status.HTTP_404_NOT_FOUND:
            error_type = "Not Found"
        elif status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
            error_type = "Validation Error"
        elif status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            error_type = "Too Many Requests"
        
        # Create the response
        content = {
            "success": False,
            "error": {
                "type": error_type,
                "detail": error_detail,
                "status_code": status_code
            }
        }
        
        # Add validation errors if available
        if hasattr(exception, "errors"):
            content["error"]["errors"] = exception.errors
        
        return JSONResponse(
            status_code=status_code,
            content=content
        )


# Context manager for request logging
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging request information"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """Log request details and timing"""
        import time
        
        # Generate request ID
        request_id = f"{time.time():.0f}-{id(request)}"
        
        # Extract client info
        client_host = request.client.host if request.client else "unknown"
        client_port = request.client.port if request.client else 0
        
        # Log request start
        logger.info(f"Request {request_id}: {request.method} {request.url.path} from {client_host}:{client_port}")
        
        # Process request with timing
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log request completion
        logger.info(f"Request {request_id} completed: {response.status_code} in {process_time:.3f}s")
        
        # Add timing header
        response.headers["X-Process-Time"] = f"{process_time:.3f}"
        
        return response


# Add global exception handler for validation errors
async def validation_exception_handler(request: Request, exc):
    """Handle validation errors from request models"""
    logger.warning(f"Validation error: {exc.errors()}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "type": "Validation Error",
                "detail": "Invalid request parameters",
                "errors": exc.errors(),
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY
            }
        }
    )