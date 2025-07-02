# user_db.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from loguru import logger
from typing import Optional
from utils.db.base import (
    Base,
    Session,
)  # Assuming you have a base.py with these defined

# Import the engine from your conversation file or from a shared base file

# Set up logging
logger.add("./logs/user_db.log", rotation="1 week")


class User(Base):
    """Database model for user information"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone_number = Column(String(20), nullable=True)
    password_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

    # Use string reference for the relationship to avoid circular imports
    conversations = relationship("Conversation", back_populates="user")

    def set_password(self, password: str) -> None:
        """Create hashed password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Check hashed password"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class UserManager:
    """Handles user operations including login and registration"""

    def create_user(
        self,
        db: Session,
        username: str,
        email: str,
        password: str,
        phone_number: Optional[str] = None,
    ) -> Optional[User]:
        """Create a new user account"""
        try:
            # Check if username or email already exists
            if (
                db.query(User)
                .filter((User.username == username) | (User.email == email))
                .first()
            ):
                logger.warning(f"Username {username} or email {email} already exists")
                return None

            new_user = User(username=username, email=email, phone_number=phone_number)
            new_user.set_password(password)

            db.add(new_user)
            db.commit()
            logger.info(f"Created new user: {username}")
            return new_user
        except ValueError as e:
            db.rollback()
            logger.error(f"Error creating user: {str(e)}")
            return None

    def authenticate_user(
        self, db: Session, username_or_email: str, password: str
    ) -> Optional[User]:
        """Authenticate a user and update last login"""
        try:
            user = (
                db.query(User)
                .filter(
                    (User.username == username_or_email)
                    | (User.email == username_or_email)
                )
                .first()
            )

            if user and user.check_password(password):
                user.last_login = datetime.now()
                db.commit()
                logger.info(f"User {user.username} authenticated successfully")
                return user
            return None
        except ValueError as e:
            logger.error(f"Authentication error: {str(e)}")
            return None

    def get_user_by_id(self, db: Session, user_id: int) -> Optional[User]:
        """Retrieve a user by their ID"""
        try:
            return db.query(User).get(user_id)
        except ValueError as e:
            logger.error(f"Error getting user by ID: {str(e)}")
            return None

    def update_user(self, db: Session, user_id: int, **kwargs) -> Optional[User]:
        """Update user information"""
        try:
            user = db.query(User).get(user_id)
            if not user:
                return None

            for key, value in kwargs.items():
                if hasattr(user, key) and key not in ["id", "password_hash"]:
                    setattr(user, key, value)

            db.commit()
            return user
        except ValueError as e:
            db.rollback()
            logger.error(f"Error updating user: {str(e)}")
            return None

    def change_password(
        self, db: Session, user_id: int, old_password: str, new_password: str
    ) -> bool:
        """Change user password"""
        try:
            user = db.query(User).get(user_id)
            if not user or not user.check_password(old_password):
                return False

            user.set_password(new_password)
            db.commit()
            return True
        except ValueError as e:
            db.rollback()
            logger.error(f"Error changing password: {str(e)}")
            return False

    def __del__(self):
        """Clean up session when manager is destroyed"""
        db.close()
