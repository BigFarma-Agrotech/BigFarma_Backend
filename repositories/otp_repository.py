from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from features.auth.models import OTPCode, OTPMedium
from config import settings
from repositories.base_repository import BaseRepository

class OTPRepository(BaseRepository[OTPCode, None, None]):
    def __init__(self, db: Session):
        super().__init__(OTPCode, db)

    def create(self, user_id: int, code: str, medium: OTPMedium, expires_in_minutes: int = None) -> Optional[OTPCode]:
        if expires_in_minutes is None:
            expires_in_minutes = settings.OTP_EXPIRE_MINUTES
            
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
        
        # Invalidate existing OTPs
        self.db.query(OTPCode).filter(
            OTPCode.user_id == user_id, 
            OTPCode.medium == medium,
            OTPCode.is_used == False
        ).update({"is_used": True})
        
        otp_record = OTPCode(
            user_id=user_id,
            code=code,
            medium=medium,
            expires_at=expires_at
        )
        
        self.db.add(otp_record)
        self.db.commit()
        self.db.refresh(otp_record)
        return otp_record

    def get_valid_otp(self, user_id: int, code: str, medium: OTPMedium) -> Optional[OTPCode]:
        return self.db.query(OTPCode).filter(
            OTPCode.user_id == user_id,
            OTPCode.code == code,
            OTPCode.medium == medium,
            OTPCode.is_used == False
        ).first()

    def mark_as_used(self, otp_id: int) -> bool:
        otp_record = self.db.query(OTPCode).filter(OTPCode.id == otp_id).first()
        if otp_record:
            otp_record.is_used = True
            self.db.commit()
            return True
        return False