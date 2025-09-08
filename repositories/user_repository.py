from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from typing import Optional, List, Dict, Any
import re
import logging

from features.auth.models import User
from features.auth.schemas import UserCreate
from repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)

class UserRepository(BaseRepository[User, UserCreate, UserCreate]):
    def __init__(self, db: Session):
        super().__init__(User, db)

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_phone(self, phone_number: str) -> Optional[User]:
        return self.db.query(User).filter(User.phone_number == phone_number).first()

    def get_by_login(self, login: str) -> Optional[User]:
        if re.match(r'^[^@]+@[^@]+\.[^@]+$', login):
            return self.get_by_email(login)
        else:
            return self.get_by_phone(login)

    def get_with_profile(self, user_id: int) -> Optional[User]:
        return self.db.query(User).options(
            joinedload(User.farmer_profile),
            joinedload(User.consumer_profile)
        ).filter(User.id == user_id).first()

    def create(self, obj_in: UserCreate, hashed_password: str) -> User:
        db_user = User(
            email=obj_in.email,
            phone_number=obj_in.phone_number,
            password=hashed_password,
            category=obj_in.category
        )
        
        try:
            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)
            return db_user
        except IntegrityError:
            self.db.rollback()
            raise ValueError("User with this email or phone number already exists")

    def update(self, id: int, **kwargs) -> Optional[User]:
        db_user = self.get(id)
        if db_user:
            for key, value in kwargs.items():
                if hasattr(db_user, key):
                    setattr(db_user, key, value)
            self.db.commit()
            self.db.refresh(db_user)
        return db_user

    def authenticate(self, login: str, password: str) -> Optional[User]:
        from core.security import verify_password
        
        db_user = self.get_by_login(login)
        if not db_user or not verify_password(password, db_user.password):
            return None
        return db_user