"""Authentication endpoints"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Response, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import bcrypt
import jwt

from app.models.user import User, UserCreate
from app.repositories.user_repository import UserRepository
from app.config import settings
from app.database.exceptions import ItemNotFoundError, DuplicateItemError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer(auto_error=False)

# Request/Response models
class LoginRequest(BaseModel):
    emailOrUsername: str = Field(..., description="Email or username")
    password: str = Field(..., min_length=6, description="Password")

class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(...)
    password: str = Field(..., min_length=6)

class AuthResponse(BaseModel):
    token: str
    user: dict

class UserProfile(BaseModel):
    userId: str
    username: str
    email: str
    createdAt: datetime

# Initialize repository
user_repo = UserRepository()

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(user_id: str, username: str) -> str:
    """Create a JWT access token"""
    payload = {
        "sub": user_id,
        "username": username,
        "exp": datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[User]:
    """Get current user from JWT token"""
    if not credentials:
        return None
    
    payload = verify_token(credentials.credentials)
    if not payload:
        return None
    
    try:
        user = await user_repo.get_user_by_id(payload["sub"])
        return user
    except Exception:
        return None

@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignupRequest, response: Response):
    """Create a new user account"""
    try:
        # Hash the password
        password_hash = hash_password(request.password)
        
        # Create user
        user_create = UserCreate(
            username=request.username,
            email=request.email,
            password=request.password  # This will be validated but not stored
        )
        
        # Create user with hashed password
        created_user = await user_repo.create_user(user_create, password_hash)
        
        # Create JWT token
        token = create_access_token(created_user.userId, created_user.username)
        
        # Set HTTP-only cookie
        response.set_cookie(
            key="cg_session",
            value=token,
            httponly=True,
            secure=settings.is_production,
            samesite="lax",
            max_age=settings.jwt_expiration_hours * 3600
        )
        
        return AuthResponse(
            token=token,
            user={
                "userId": created_user.userId,
                "username": created_user.username
            }
        )
        
    except DuplicateItemError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, response: Response):
    """Login with email/username and password"""
    try:
        # Try to find user by email first, then by username
        user = await user_repo.get_user_by_email(request.emailOrUsername)
        if not user:
            # Try by username (search in database)
            query = "SELECT * FROM c WHERE c.username = @username"
            parameters = [{"name": "@username", "value": request.emailOrUsername}]
            results = await user_repo.query(query, parameters)
            if results:
                user = User(**results[0])
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Verify password
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Create JWT token
        token = create_access_token(user.userId, user.username)
        
        # Set HTTP-only cookie
        response.set_cookie(
            key="cg_session",
            value=token,
            httponly=True,
            secure=settings.is_production,
            samesite="lax",
            max_age=settings.jwt_expiration_hours * 3600
        )
        
        return AuthResponse(
            token=token,
            user={
                "userId": user.userId,
                "username": user.username
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/me", response_model=UserProfile)
async def get_me(request: Request, current_user: Optional[User] = Depends(get_current_user)):
    """Get current user profile"""
    # Try to get user from cookie if not from header
    if not current_user:
        token = request.cookies.get("cg_session")
        if token:
            payload = verify_token(token)
            if payload:
                try:
                    current_user = await user_repo.get_user_by_id(payload["sub"])
                except Exception:
                    pass
    
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return UserProfile(
        userId=current_user.userId,
        username=current_user.username,
        email=current_user.email,
        createdAt=current_user.created_at
    )

@router.post("/logout")
async def logout(response: Response):
    """Logout user"""
    response.delete_cookie(key="cg_session")
    return {"message": "Logged out successfully"}