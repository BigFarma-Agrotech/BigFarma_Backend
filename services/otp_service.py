import logging
import asyncio
from datetime import datetime, timezone

from features.auth.models import OTPMedium
from utils.helpers import generate_otp_code
from repositories import OTPRepository
from services.email_service import EmailService
from services.sms_service import SMSService

logger = logging.getLogger(__name__)

class OTPService:
    def __init__(self, db):
        self.db = db
        self.otp_repo = OTPRepository(db)
        self.email_service = EmailService()
        self.sms_service = SMSService()
    
    async def request_otp(self, user_id: int, medium: OTPMedium, destination: str, otp_type: str) -> bool:
        try:
            otp_code = generate_otp_code()
            self.otp_repo.create(user_id, otp_code, medium, otp_type)
            
            if medium == OTPMedium.EMAIL:
                return await self.email_service.send_otp_email(destination, otp_code, otp_type)
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, self.sms_service.send_otp_sms, destination, otp_code, otp_type)
        except Exception as e:
            logger.error(f"OTP request error: {e}")
            return False
    
    def verify_otp(self, user_id: int, code: str, medium: OTPMedium, otp_type: str) -> bool:
        try:
            otp_record = self.otp_repo.get_valid_otp(user_id, code, medium, otp_type)
            if otp_record and otp_record.expires_at > datetime.now(timezone.utc):
                # Mark OTP as verified (but don't delete yet - wait for completion)
                success = self.otp_repo.mark_as_verified(otp_record.id)
                return success
            return False
        except Exception as e:
            logger.error(f"OTP verification error: {e}")
            return False
    
    def is_otp_verified(self, user_id: int, medium: OTPMedium, otp_type: str) -> bool:
        """Check if OTP has been verified for this user and type"""
        return self.otp_repo.is_verified(user_id, medium, otp_type)
    
    def delete_verified_otp(self, user_id: int, medium: OTPMedium, otp_type: str) -> bool:
        """Delete verified OTP after successful operation"""
        return self.otp_repo.delete_verified(user_id, medium, otp_type)
