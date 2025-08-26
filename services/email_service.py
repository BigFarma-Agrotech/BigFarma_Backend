import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import aiosmtplib
from ssl import SSLError

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
            
            # Send email asynchronously with proper TLS handling
            smtp = aiosmtplib.SMTP(hostname=settings.SMTP_HOST, port=settings.SMTP_PORT)
            await smtp.connect()
            
            # Only start TLS if needed and if the server supports it
            if settings.SMTP_USE_TLS:
                try:
                    # Check if the connection is already secure
                    if not smtp.is_connected or not getattr(smtp, '_tls_established', False):
                        await smtp.starttls()
                except SSLError as ssl_error:
                    if "already using TLS" in str(ssl_error).lower():
                        logger.debug("Connection already using TLS, continuing...")
                    else:
                        raise ssl_error
                except Exception as e:
                    if "already using TLS" in str(e).lower() or "already secure" in str(e).lower():
                        logger.debug("Connection already secure, continuing...")
                    else:
                        raise e
            
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            await smtp.sendmail(settings.SMTP_USER, email, msg.as_string())
            await smtp.quit()
            
            logger.info(f"OTP email sent successfully to {email} for {otp_type}")
            return True
                
        except Exception as e:
            logger.error(f"Error sending OTP email to {email}: {e}")
            return False

    async def send_verification_submission_email(self, email: str, user_id: int, profile_id: int) -> bool:
        """Send email notification that farmer profile is submitted for verification."""
        try:
            if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
                logger.warning("SMTP credentials not configured.")
                return False
            
            msg = MIMEMultipart()
            msg['From'] = settings.SMTP_USER
            msg['To'] = email
            msg['Subject'] = f"{settings.APP_NAME} - Profile Submitted for Verification"
            
            body = f"""
            <html>
            <body>
                <h2>Thank You for Submitting Your Profile!</h2>
                <p>Dear Farmer,</p>
                <p>Your profile has been successfully submitted for verification.</p>
                <p><strong>What happens next?</strong></p>
                <ul>
                    <li>Our team will review your profile information</li>
                    <li>We'll verify your identification documents</li>
                    <li>This process typically takes 1-2 business days</li>
                </ul>
                <p>You'll receive an email and SMS notification once your account has been verified.</p>
                <p>If you have any questions, please contact our support team.</p>
                <br>
                <p>Best regards,<br>{settings.APP_NAME} Team</p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Send email asynchronously with proper TLS handling
            smtp = aiosmtplib.SMTP(hostname=settings.SMTP_HOST, port=settings.SMTP_PORT)
            await smtp.connect()
            
            # Only start TLS if needed and if the server supports it
            if settings.SMTP_USE_TLS:
                try:
                    # Check if the connection is already secure
                    if not smtp.is_connected or not getattr(smtp, '_tls_established', False):
                        await smtp.starttls()
                except SSLError as ssl_error:
                    if "already using TLS" in str(ssl_error).lower():
                        logger.debug("Connection already using TLS, continuing...")
                    else:
                        raise ssl_error
                except Exception as e:
                    if "already using TLS" in str(e).lower() or "already secure" in str(e).lower():
                        logger.debug("Connection already secure, continuing...")
                    else:
                        raise e
            
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            await smtp.sendmail(settings.SMTP_USER, email, msg.as_string())
            await smtp.quit()
            
            logger.info(f"Verification submission email sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending verification submission email to {email}: {e}")
            return False

    async def send_verification_complete_email(self, email: str, user_id: int) -> bool:
        """Send email notification that farmer profile has been verified."""
        try:
            if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
                logger.warning("SMTP credentials not configured.")
                return False
            
            msg = MIMEMultipart()
            msg['From'] = settings.SMTP_USER
            msg['To'] = email
            msg['Subject'] = f"{settings.APP_NAME} - Account Verified Successfully!"
            
            body = f"""
            <html>
            <body>
                <h2>Congratulations! Your Account is Now Verified</h2>
                <p>Dear Farmer,</p>
                <p>We're excited to inform you that your {settings.APP_NAME} account has been successfully verified!</p>
                <p><strong>What you can do now:</strong></p>
                <ul>
                    <li>List your farm products for sale</li>
                    <li>Connect with consumers in your area</li>
                    <li>Access exclusive farmer resources</li>
                    <li>Join our farming community</li>
                </ul>
                <p>Log in to your account to get started and explore all the features available to verified farmers.</p>
                <p>If you have any questions, our support team is here to help.</p>
                <br>
                <p>Welcome to the {settings.APP_NAME} community!<br>{settings.APP_NAME} Team</p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Send email asynchronously with proper TLS handling
            smtp = aiosmtplib.SMTP(hostname=settings.SMTP_HOST, port=settings.SMTP_PORT)
            await smtp.connect()
            
            # Only start TLS if needed and if the server supports it
            if settings.SMTP_USE_TLS:
                try:
                    # Check if the connection is already secure
                    if not smtp.is_connected or not getattr(smtp, '_tls_established', False):
                        await smtp.starttls()
                except SSLError as ssl_error:
                    if "already using TLS" in str(ssl_error).lower():
                        logger.debug("Connection already using TLS, continuing...")
                    else:
                        raise ssl_error
                except Exception as e:
                    if "already using TLS" in str(e).lower() or "already secure" in str(e).lower():
                        logger.debug("Connection already secure, continuing...")
                    else:
                        raise e
            
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            await smtp.sendmail(settings.SMTP_USER, email, msg.as_string())
            await smtp.quit()
            
            logger.info(f"Verification complete email sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending verification complete email to {email}: {e}")
            return False