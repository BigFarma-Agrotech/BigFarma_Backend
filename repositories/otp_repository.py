from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from features.auth.models import OTPCode, OTPMedium
from config import settings
from repositories.base_repository import BaseRepository

class OTPRepository(BaseRepository[OTPCode, None, None]):
    def __init__(self, db: Session):
        super().__init__(OTPCode, db)

    def create(self, user_id: int, code: str, medium: OTPMedium, otp_type: str, expires_in_minutes: int = None) -> Optional[OTPCode]:
        if expires_in_minutes is None:
            expires_in_minutes = settings.OTP_EXPIRE_MINUTES
            
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
        
        # Delete any existing OTPs of the same type for this user
        self.db.query(OTPCode).filter(
            OTPCode.user_id == user_id, 
            OTPCode.medium == medium,
            OTPCode.otp_type == otp_type
        ).delete()
        
        otp_record = OTPCode(
            user_id=user_id,
            code=code,
            medium=medium,
            otp_type=otp_type,
            expires_at=expires_at,
            is_verified=False
        )
        
        self.db.add(otp_record)
        self.db.commit()
        self.db.refresh(otp_record)
        return otp_record

    def get_valid_otp(self, user_id: int, code: str, medium: OTPMedium, otp_type: str) -> Optional[OTPCode]:
        return self.db.query(OTPCode).filter(
            OTPCode.user_id == user_id,
            OTPCode.code == code,
            OTPCode.medium == medium,
            OTPCode.otp_type == otp_type,
            OTPCode.is_verified == False,
            OTPCode.expires_at > datetime.now(timezone.utc)
        ).first()

    def mark_as_verified(self, otp_id: int) -> bool:
        otp_record = self.db.query(OTPCode).filter(OTPCode.id == otp_id).first()
        if otp_record:
            otp_record.is_verified = True
            self.db.commit()
            return True
        return False

    def is_verified(self, user_id: int, medium: OTPMedium, otp_type: str) -> bool:
        """Check if there's a verified OTP for this user and type"""
        return self.db.query(OTPCode).filter(
            OTPCode.user_id == user_id,
            OTPCode.medium == medium,
            OTPCode.otp_type == otp_type,
            OTPCode.is_verified == True,
            OTPCode.expires_at > datetime.now(timezone.utc)
        ).first() is not None

    def delete_verified(self, user_id: int, medium: OTPMedium, otp_type: str) -> bool:
        """Delete verified OTP after successful operation"""
        result = self.db.query(OTPCode).filter(
            OTPCode.user_id == user_id,
            OTPCode.medium == medium,
            OTPCode.otp_type == otp_type,
            OTPCode.is_verified == True
        ).delete()
        self.db.commit()
        return result > 0

    def get_user_otps(self, user_id: int, skip: int = 0, limit: int = 100) -> List[OTPCode]:
        return self.db.query(OTPCode).filter(OTPCode.user_id == user_id).offset(skip).limit(limit).all()