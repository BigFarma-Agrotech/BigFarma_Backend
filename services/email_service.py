import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import aiosmtplib

from config import settings

logger = logging.getLogger(__name__)

class EmailService:
    async def send_otp_email(self, email: str, otp_code: str, otp_type: str = "verification") -> bool:
        """Send OTP code via email asynchronously."""
        try:
            # Check if SMTP is configured
            if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
                logger.warning("SMTP credentials not configured. OTP code: %s", otp_code)
                return False
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = settings.SMTP_USER
            msg['To'] = email
            
            # Set subject and body based on OTP type
            if otp_type == "password_reset":
                msg['Subject'] = f"{settings.APP_NAME} - Password Reset OTP"
                body = f"""
                <html>
                <body>
                    <h2>{settings.APP_NAME} Password Reset</h2>
                    <p>You requested a password reset for your {settings.APP_NAME} account.</p>
                    <p>Your password reset code is: <strong style="font-size: 24px; color: #dc3545;">{otp_code}</strong></p>
                    <p>This code will expire in {settings.OTP_EXPIRE_MINUTES} minutes.</p>
                    <p>If you didn't request this password reset, please ignore this email and your password will remain unchanged.</p>
                    <br>
                    <p>Best regards,<br>{settings.APP_NAME} Team</p>
                </body>
                </html>
                """
            else:
                msg['Subject'] = f"{settings.APP_NAME} - Verification OTP"
                body = f"""
                <html>
                <body>
                    <h2>{settings.APP_NAME} Verification</h2>
                    <p>You requested a verification code for your {settings.APP_NAME} account.</p>
                    <p>Your verification code is: <strong style="font-size: 24px; color: #007bff;">{otp_code}</strong></p>
                    <p>This code will expire in {settings.OTP_EXPIRE_MINUTES} minutes.</p>
                    <p>If you didn't request this code, please ignore this email.</p>
                    <br>
                    <p>Best regards,<br>{settings.APP_NAME} Team</p>
                </body>
                </html>
                """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Send email asynchronously
            smtp = aiosmtplib.SMTP(hostname=settings.SMTP_HOST, port=settings.SMTP_PORT)
            await smtp.connect()
            if settings.SMTP_USE_TLS:
                await smtp.starttls()
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            await smtp.sendmail(settings.SMTP_USER, email, msg.as_string())
            await smtp.quit()
            
            logger.info(f"OTP email sent successfully to {email} for {otp_type}")
            return True
                
        except Exception as e:
            logger.error(f"Error sending OTP email to {email}: {e}")
            return False