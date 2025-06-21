# app/middleware/auth_middleware.py
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
import os
from dotenv import load_dotenv

#load env variables
load_dotenv()


async def auth_middleware(request: Request, call_next):
    # List of public routes that don't require authentication
    public_routes = [
        "/auth/login",
        "/auth/register",
        "/auth/register-page",
        "/webhooks",
        "/static"  # Allow static files
    ]
    
    # Skip auth check for public routes
    if any(request.url.path.startswith(route) for route in public_routes):
        return await call_next(request)
    
    # Check for token in cookies
    token = request.cookies.get("access_token")
    if not token:
        if request.url.path.startswith("/api"):
            raise HTTPException(
                status_code=401,
                detail="Not authenticated"
            )
        return RedirectResponse(url="/auth/login")
    
    try:
        # Verify token
        payload = jwt.decode(
            token.split()[1],  # Remove "Bearer " prefix
            os.getenv("SECRET_KEY"),
            algorithms=[os.getenv("ALGORITHM")]
        )
        request.state.user = payload.get("sub")
    except JWTError:
        if request.url.path.startswith("/api"):
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )
        response = RedirectResponse(url="/auth/login")
        response.delete_cookie("access_token")
        return response
    
    return await call_next(request)