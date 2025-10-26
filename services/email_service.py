import logging
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import datetime

from config import settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.templates_dir = Path(__file__).parent.parent / "templates" / "emails"
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=True
        )
        self.current_year = datetime.datetime.now().year
    
    def _render_template(self, template_name: str, **context) -> str:
        """Render HTML template with given context"""
        try:
            template = self.jinja_env.get_template(template_name)
            default_context = {
                'app_name': settings.APP_NAME,
                'expire_minutes': settings.OTP_EXPIRE_MINUTES,
                'current_year': self.current_year
            }
            default_context.update(context)
            return template.render(**default_context)
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {e}")
            return self._create_fallback_email(**context)
    
    def _create_fallback_email(self, **context) -> str:
        """Create fallback email content if template rendering fails"""
        otp_code = context.get('otp_code', '')
        otp_type = context.get('otp_type', 'verification')
        app_name = context.get('app_name', settings.APP_NAME)
        expire_minutes = context.get('expire_minutes', settings.OTP_EXPIRE_MINUTES)
        
        if otp_type == 'password_reset':
            return f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #4CAF50; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0;">
                    <h1>{app_name}</h1>
                </div>
                <div style="background-color: #f9f9f9; padding: 20px; border-radius: 0 0 5px 5px; border: 1px solid #ddd;">
                    <h2>Password Reset Request</h2>
                    <p>Dear User,</p>
                    <p>You requested a password reset for your {app_name} account.</p>
                    <p>Please use the following verification code to reset your password:</p>
                    
                    <div style="font-size: 24px; font-weight: bold; color: #4CAF50; text-align: center; margin: 20px 0; padding: 15px; background-color: #f0f8f0; border-radius: 5px; border: 2px dashed #4CAF50;">
                        {otp_code}
                    </div>
                    
                    <p>This code will expire in {expire_minutes} minutes.</p>
                    <p>If you didn't request this password reset, please ignore this email and your password will remain unchanged.</p>
                    
                    <p>Stay secure!</p>
                    <p><strong>The {app_name} Team</strong></p>
                </div>
                <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #666;">
                    <p>If you didn't request this email, please ignore it.</p>
                    <p>&copy; {self.current_year} {app_name}. All rights reserved.</p>
                </div>
            </body>
            </html>
            """
        else:
            return f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #4CAF50; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0;">
                    <h1>{app_name}</h1>
                </div>
                <div style="background-color: #f9f9f9; padding: 20px; border-radius: 0 0 5px 5px; border: 1px solid #ddd;">
                    <h2>Verify Your Account</h2>
                    <p>Dear User,</p>
                    <p>You requested a verification code for your {app_name} account.</p>
                    <p>Please use the following verification code to complete your account verification:</p>
                    
                    <div style="font-size: 24px; font-weight: bold; color: #4CAF50; text-align: center; margin: 20px 0; padding: 15px; background-color: #f0f8f0; border-radius: 5px; border: 2px dashed #4CAF50;">
                        {otp_code}
                    </div>
                    
                    <p>This code will expire in {expire_minutes} minutes.</p>
                    <p>If you didn't request this code, please ignore this email and your account will remain secure.</p>
                    
                    <p>Thank you for choosing {app_name}!</p>
                    <p><strong>The {app_name} Team</strong></p>
                </div>
                <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #666;">
                    <p>If you didn't request this email, please ignore it.</p>
                    <p>&copy; {self.current_year} {app_name}. All rights reserved.</p>
                </div>
            </body>
            </html>
            """
    
    async def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send email with HTML content"""
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning("SMTP credentials not configured.")
            return False
        
        smtp = None
        try:
            msg = MIMEMultipart()
            msg['From'] = settings.SMTP_USER
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(html_content, 'html'))
            
            # Use TLS setting properly
            use_tls = getattr(settings, 'SMTP_USE_TLS', True)
            smtp = aiosmtplib.SMTP(
                hostname=settings.SMTP_HOST, 
                port=settings.SMTP_PORT,
                use_tls=use_tls
            )
            
            await smtp.connect()
            
            # Only attempt STARTTLS if not already using TLS and it's requested
            if use_tls and not smtp.is_connected_with_tls:
                await smtp.starttls()
            
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            await smtp.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return False
        finally:
            if smtp:
                try:
                    await smtp.quit()
                except Exception as e:
                    logger.warning(f"Error closing SMTP connection: {e}")
    
    async def send_welcome_email(self, to_email: str, user_name: str) -> bool:
        """Send welcome email after successful account creation"""
        html_content = self._render_template(
            'welcome.html',
            user_name=user_name
        )
        
        subject = f"Welcome to {settings.APP_NAME}!"
        return await self.send_email(to_email, subject, html_content)
    
    async def send_otp_email(self, to_email: str, otp_code: str, otp_type: str = "verification") -> bool:
        """Send OTP email for verification or password reset"""
        if otp_type == "password_reset":
            html_content = self._render_template(
                'password_reset.html',
                otp_code=otp_code,
                otp_type=otp_type
            )
            subject = f"{settings.APP_NAME} - Password Reset OTP"
        else:
            html_content = self._render_template(
                'verification.html',
                otp_code=otp_code,
                otp_type=otp_type
            )
            subject = f"{settings.APP_NAME} - Verification OTP"
        
        return await self.send_email(to_email, subject, html_content)
    
    async def send_verification_success_email(self, to_email: str, user_name: str) -> bool:
        """Send email when account is successfully verified"""
        html_content = self._render_template(
            'verification_success.html',  # Consider creating a dedicated template
            user_name=user_name
        )
        
        subject = f"{settings.APP_NAME} - Account Verified Successfully!"
        return await self.send_email(to_email, subject, html_content)


# Create a singleton instance for easy import
email_service = EmailService()
