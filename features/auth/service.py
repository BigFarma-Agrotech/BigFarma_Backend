import logging
from typing import Optional
import re

from features.auth.models import User, OTPMedium
from features.auth.schemas import UserCreate
from repositories.user_repository import UserRepository
from services.otp_service import OTPService

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, db):
        self.db = db
        self.user_repo = UserRepository(db)
        self.otp_service = OTPService(db)
    
    def get_user_by_identifier(self, identifier: str) -> Optional[User]:
        """Get user by email or phone number."""
        return self.user_repo.get_by_login(identifier)
    
    def authenticate_user(self, login: str, password: str) -> Optional[User]:
        """Authenticate user with login and password."""
        return self.user_repo.authenticate(login, password)
    
    def create_user(self, user_data: UserCreate) -> User:
        """Create a new user."""
        from core.security import get_password_hash
        
        hashed_password = get_password_hash(user_data.password)
        return self.user_repo.create(user_data, hashed_password)
    
    async def request_otp(
        self, 
        user_id: int, 
        medium: OTPMedium, 
        destination: str, 
        otp_type: str = "verification"
    ) -> bool:
        """Request OTP code via specified medium."""
        return await self.otp_service.request_otp(user_id, medium, destination, otp_type)
    
    def verify_otp(self, user_id: int, code: str, medium: OTPMedium) -> bool:
        """Verify OTP code."""
        return self.otp_service.verify_otp(user_id, code, medium)