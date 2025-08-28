import logging
from typing import Optional

from features.auth.models import User, OTPMedium
from features.auth.schemas import UserCreate
from repositories import UserRepository
from services.otp_service import OTPService

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, db):
        self.db = db
        self.user_repo = UserRepository(db)
        self.otp_service = OTPService(db)
    
    def get_user_by_email_or_phone(self, email: Optional[str] = None, phone: Optional[str] = None) -> Optional[User]:
        if email:
            return self.user_repo.get_by_email(email)
        elif phone:
            return self.user_repo.get_by_phone(phone)
        return None
    
    def authenticate_user(self, login: str, password: str) -> Optional[User]:
        return self.user_repo.authenticate(login, password)
    
    def create_user(self, user_data: UserCreate) -> User:
        from core.security import get_password_hash
        hashed_password = get_password_hash(user_data.password)
        return self.user_repo.create(user_data, hashed_password)
    
    async def request_otp(self, user_id: int, medium: OTPMedium, email: str = None, phone: str = None, otp_type: str = "verification") -> bool:
        destination = email if medium == OTPMedium.EMAIL else phone
        return await self.otp_service.request_otp(user_id, medium, destination, otp_type)
    
    def verify_otp(self, user_id: int, code: str, medium: OTPMedium) -> bool:
        return self.otp_service.verify_otp(user_id, code, medium)
    
    def mark_user_verified(self, user_id: int) -> bool:
        user = self.user_repo.update(user_id, is_verified=True)
        return user is not None