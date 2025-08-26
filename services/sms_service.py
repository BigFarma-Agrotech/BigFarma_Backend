import logging
from twilio.rest import Client

from config import settings

logger = logging.getLogger(__name__)

class SMSService:
    def __init__(self):
        self.twilio_client = None
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            self.twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    
    def send_otp_sms(self, phone_number: str, otp_code: str, otp_type: str = "verification") -> bool:
        """Send OTP code via SMS."""
        try:
            if not self.twilio_client:
                logger.warning("Twilio not configured. OTP code: %s", otp_code)
                return False
            
            # Create message content based on OTP type
            if otp_type == "password_reset":
                message_body = f"Your {settings.APP_NAME} password reset code is: {otp_code}. It expires in {settings.OTP_EXPIRE_MINUTES} minutes."
            else:
                message_body = f"Your {settings.APP_NAME} verification code is: {otp_code}. It expires in {settings.OTP_EXPIRE_MINUTES} minutes."
            
            # Send SMS
            message = self.twilio_client.messages.create(
                body=message_body,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone_number
            )
            
            logger.info(f"OTP SMS sent successfully to {phone_number}, SID: {message.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending OTP SMS to {phone_number}: {e}")
            return False