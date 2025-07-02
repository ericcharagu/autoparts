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

from utils.db.base import Session, get_db
from utils.db.conversation_db import Conversation
from utils.db.user_db import User, UserManager


# Loading env and its variables
load_dotenv()
ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")


# Initialize templates
templates = Jinja2Templates(directory="templates/auth")

# logging errors
logger.add("./logs/auth_logs.log", rotation="1 week")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


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
        orm_mode = True


# Utility functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def get_user(username: str) -> Optional[User]:
    db = Session()
    user = db.query(User).filter(User.username == username).first()
    db.close()
    return user


def authenticate_user(username: str, password: str, db: Session):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(days=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
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


router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    responses={401: {"description": "Not authorized"}},
)


# API endpoints
@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(days=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # Update last login
    user.last_login = datetime.now()
    db.commit()

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register")
async def handle_registration(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    phone_number: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        # Prepare data for validation
        user_data = {
            "username": username.strip(),
            "email": email.strip(),
            "password": password,
            "phone_number": phone_number.strip() if phone_number else None,
        }

        # Validate using Pydantic model
        try:
            UserCreate(**user_data)
        except Exception as e:
            errors = []
            for error in e.errors():
                field = error["loc"][0]
                msg = error["msg"]
                errors.append(f"{field}: {msg}")
            raise HTTPException(status_code=422, detail=" ".join(errors))

        # Check for existing user
        existing_user = (
            db.query(User)
            .filter(
                (User.username == user_data["username"])
                | (User.email == user_data["email"])
            )
            .first()
        )

        if existing_user:
            raise HTTPException(
                status_code=400, detail="Username or email already exists"
            )

        # Create new user
        new_user = User(
            username=user_data["username"],
            email=user_data["email"],
            phone_number=user_data["phone_number"],
            password_hash=get_password_hash(user_data["password"]),
            created_at=datetime.now(),
            is_active=True,
        )

        db.add(new_user)
        db.commit()

        # Set success flash message
        request.session["flash"] = "Registration successful! Please login."
        return RedirectResponse(url="login", status_code=303)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login_form_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authenticate_user(username, password, db)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    access_token_expires = timedelta(days=30)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=True,  # Set to False for development without HTTPS
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
    db: Session = Depends(get_db),
):
    try:
        # Validate input
        if len(username) < 3:
            raise HTTPException(
                status_code=400, detail="Username must be at least 3 characters"
            )

        if len(password) < 8:
            raise HTTPException(
                status_code=400, detail="Password must be at least 8 characters"
            )

        # Process registration
        user_data = {
            "username": username,
            "email": email,
            "password": password,
            "phone_number": phone_number if phone_number else None,
        }

        existing_user = (
            db.query(User)
            .filter(
                (User.username == user_data["username"])
                | (User.email == user_data["email"])
            )
            .first()
        )

        if existing_user:
            return templates.TemplateResponse(
                "auth/register.html",
                {
                    "request": request,
                    "error": "Username or email already exists",
                    "form_data": user_data,  # Return form data to repopulate
                },
                status_code=400,
            )

        new_user = User(
            username=user_data["username"],
            email=user_data["email"],
            phone_number=user_data["phone_number"],
            password_hash=get_password_hash(user_data["password"]),
            created_at=datetime.now(),
            is_active=True,
        )

        db.add(new_user)
        db.commit()

        return RedirectResponse(url="/auth/login?registered=true", status_code=303)

    except ValueError as e:
        db.rollback()
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": str(e), "form_data": user_data},
            status_code=400,
        )


# Protected endpoint example
@router.get("/conversations/")
async def read_conversations(current_user: User = Depends(get_current_active_user)):
    db = Session()
    try:
        conversations = (
            db.query(Conversation).filter(Conversation.user_id == current_user.id).all()
        )
        return conversations
    finally:
        db.close()
