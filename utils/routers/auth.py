# auth.py
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from loguru import logger
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import select
from utils.db.base import AsyncSession, get_db, execute_query

# from utils.db.conversation_db import Conversation
from utils.db.user_db import User

# Loading env and its variables
load_dotenv()
TOKEN_VALIDITY_DAYS = int(os.getenv("TOKEN_VALIDITY_DAYS", "30"))
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")


# Initialize templates
templates = Jinja2Templates(directory="templates/auth")

# logging errors
logger.add("./logs/auth_logs.log", rotation="1 week")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    responses={401: {"description": "Not authorized"}},
)


# Pydantic models
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    phone_number: Optional[str] = Field(None, min_length=10, max_length=15)

    class Config:
        json_schema_extra = {
            "example": {
                "username": "johndoe",
                "email": "john@example.com",
                "password": "securepassword123",
                "phone_number": "+1234567890",
            }
        }


class UserResponse(BaseModel):
    username: str
    email: str
    phone_number: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


# Utility functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def get_user(username: str) -> Optional[User]:
    db = AsyncSession()
    user = """SELECT * FROM users WHERE username=:username;"""
    db.close()
    return user


async def authenticate_user(username: str, password: str, db: AsyncSession):
    existing_user_query = select(User).where(User.username == username)
    result = await db.execute(existing_user_query)
    user = result.scalar_one_or_none()  # Use scalar_one_or_none for async
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_VALIDITY_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# =============================================================================
# API ENDPOINTS (For programmatic access, returning JSON)
# =============================================================================


# API endpoints
@router.post(
    "/token", response_model=Token, summary="Get JWT access token for API access"
)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    user = await authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(days=TOKEN_VALIDITY_DAYS)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    return {"access_token": access_token, "token_type": "bearer"}


@router.post(
    "/register/api",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user via API",
)
async def api_register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing_user_query = """SELECT * FROM users WHERE email=:user_data.email;"""
    existing_user = execute_query(existing_user_query)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        phone_number=user_data.phone_number,
        password_hash=get_password_hash(user_data.password),
        is_active=True,  # Or False, if you require email verification
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


# =============================================================================
# WEB FORM ENDPOINTS (For browser-based interaction, returning HTML/Redirects)
# =============================================================================


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login", summary="Handle login")
async def login_form_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(username, password, db)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    access_token = create_access_token(data={"sub": user.username})
    # Update last login timestamp
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=TOKEN_VALIDITY_DAYS,
        secure=True,  # Set to False for development without HTTPS
        samesite="lax",  # Good security practice
        # secure=request.url.scheme == "https", # Only set secure flag if on HTTPS and prod
    )

    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/auth/login")
    response.delete_cookie("access_token")
    return response


@router.get("/register-page", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register", response_class=HTMLResponse)
async def register_form_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    phone_number: str = Form(""),  # Empty string as default
    is_managerial: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    # Validate input
    if len(username) < 3:
        raise HTTPException(
            status_code=400, detail="Username must be at least 3 characters"
        )

    if len(password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters"
        )

    # Determine the user group based on the checkbox

    # Process registration
    user_data = {
        "username": username,
        "email": email,
        "password": password,
        "phone_number": phone_number if phone_number else None,
    }
    try:
        # existing_user_query = """SELECT * FROM users WHERE email = :email;"""
        # existing_user = execute_query(existing_user_query)
        # logger.info(existing_user)

        # if existing_user:
        #     return templates.TemplateResponse(
        #         "register.html",
        #         {
        #             "request": request,
        #             "error": "Username or email already exists",
        #             "form_data": user_data,  # Return form data to repopulate
        #         },
        #         status_code=400,
        #     )

        new_user = User(
            username=user_data["username"],
            email=user_data["email"],
            phone_number=user_data["phone_number"],
            password_hash=get_password_hash(user_data["password"]),
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )

        db.add(new_user)
        await db.commit()

        return RedirectResponse(url="/auth/login?registered=true", status_code=303)

    except ValueError as e:
        db.rollback()
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": str(e), "form_data": user_data},
            status_code=500,
        )


# Protected endpoint example
# @router.get("/conversations/")
# async def read_conversations(current_user: User = Depends(get_current_active_user)):
#     db                                          = AsyncSession()
#     try:
#         conversations                           = (
#             db.query(Conversation).filter(Conversation.user_id == current_user.id).all()
#         )
#         return conversations
#     finally:
#         db.close()
