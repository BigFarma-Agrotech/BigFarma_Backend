from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.exc import SQLAlchemyError
import logging

from features.auth.models import OTPCode, OTPMedium
from config import settings
from repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)

class OTPRepository(BaseRepository[OTPCode, None, None]):
    def __init__(self, db: Session):
        super().__init__(OTPCode, db)

    def create(self, user_id: int, code: str, medium: OTPMedium, 
               expires_in_minutes: int = None) -> Optional[OTPCode]:
        try:
            if expires_in_minutes is None:
                expires_in_minutes = settings.OTP_EXPIRE_MINUTES
                
            expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)
            
            # Invalidate any existing OTP codes for this user and medium
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
            
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def get_valid_otp(self, user_id: int, code: str, medium: OTPMedium) -> Optional[OTPCode]:
        try:
            return self.db.query(OTPCode).filter(
                OTPCode.user_id == user_id,
                OTPCode.code == code,
                OTPCode.medium == medium,
                OTPCode.is_used == False,
                OTPCode.expires_at > datetime.utcnow()
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_valid_otp: {e}")
            return None

    def mark_as_used(self, otp_id: int) -> bool:
        try:
            otp_record = self.db.query(OTPCode).filter(OTPCode.id == otp_id).first()
            if otp_record:
                otp_record.is_used = True
                self.db.commit()
                return True
            return False
        except SQLAlchemyError:
            self.db.rollback()
            return False

    def get_user_otps(self, user_id: int, skip: int = 0, limit: int = 100) -> List[OTPCode]:
        try:
            return self.db.query(OTPCode).filter(OTPCode.user_id == user_id).offset(skip).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_user_otps: {e}")
            return []