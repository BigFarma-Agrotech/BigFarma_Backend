import logging
import asyncio
from typing import Optional
from sqlalchemy.exc import SQLAlchemyError

from config import settings
from features.auth.models import OTPMedium
from utils.helpers import generate_otp_code
from repositories.otp_repository import OTPRepository
from services.email_service import EmailService
from services.sms_service import SMSService

logger = logging.getLogger(__name__)

class OTPService:
    def __init__(self, db):
        self.db = db
        self.otp_repo = OTPRepository(db)
        self.email_service = EmailService()
        self.sms_service = SMSService()
    
    async def request_otp(
        self, 
        user_id: int, 
        medium: OTPMedium, 
        destination: str, 
        otp_type: str = "verification"
    ) -> bool:
        """Request OTP code via specified medium."""
        try:
            # Generate OTP code
            otp_code = generate_otp_code()
            
            # Create OTP record in database
            self.otp_repo.create(user_id, otp_code, medium)
            self.db.commit()
            
            # Send OTP via appropriate medium
            if medium == OTPMedium.EMAIL:
                return await self.email_service.send_otp_email(destination, otp_code, otp_type)
            elif medium == OTPMedium.PHONE:
                # Run SMS sending in thread pool since it's synchronous
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, 
                    self.sms_service.send_otp_sms, 
                    destination, 
                    otp_code, 
                    otp_type
                )
            return False
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error in OTP request: {e}")
            return False
        except Exception as e:
            logger.error(f"Error in OTP request: {e}")
            return False
    
    def verify_otp(self, user_id: int, code: str, medium: OTPMedium) -> bool:
        """Verify OTP code."""
        try:
            otp_record = self.otp_repo.get_valid_otp(user_id, code, medium)
            if otp_record:
                self.otp_repo.mark_as_used(otp_record.id)
                self.db.commit()
                return True
            return False
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error in OTP verification: {e}")
            return False
        except Exception as e:
            logger.error(f"Error in OTP verification: {e}")
            return False