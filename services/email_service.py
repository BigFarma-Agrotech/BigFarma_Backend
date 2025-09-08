import logging
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from jinja2 import Template
import os

from config import settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.templates_dir = Path(__file__).parent.parent / "templates"
    
    def _render_template(self, template_name: str, **context) -> str:
        """Render HTML template with given context"""
        try:
            template_path = self.templates_dir / template_name
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            template = Template(template_content)
            default_context = {
                'app_name': settings.APP_NAME,
                'expire_minutes': settings.OTP_EXPIRE_MINUTES
            }
            default_context.update(context)
            
            return template.render(**default_context)
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {e}")
            # Fallback to simple text
            return self._create_fallback_email(**context)
    
    def _create_fallback_email(self, **context) -> str:
        """Create fallback email content if template rendering fails"""
        otp_code = context.get('otp_code', '')
        otp_type = context.get('otp_type', 'verification')
        
        if otp_type == 'verification':
            return f"""
            <h2>{settings.APP_NAME} Verification</h2>
            <p>Your verification code is: <strong>{otp_code}</strong></p>
            <p>This code will expire in {settings.OTP_EXPIRE_MINUTES} minutes.</p>
            """
        else:
            return f"""
            <h2>{settings.APP_NAME} Password Reset</h2>
            <p>Your password reset code is: <strong>{otp_code}</strong></p>
            <p>This code will expire in {settings.OTP_EXPIRE_MINUTES} minutes.</p>
            """
    
    async def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send email with HTML content"""
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning("SMTP credentials not configured.")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = settings.SMTP_USER
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(html_content, 'html'))
            
            smtp = aiosmtplib.SMTP(hostname=settings.SMTP_HOST, port=settings.SMTP_PORT)
            await smtp.connect()
            
            if settings.SMTP_USE_TLS:
                try:
                    await smtp.starttls()
                except:
                    pass  # Ignore TLS errors if already secure
            
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            await smtp.sendmail(settings.SMTP_USER, to_email, msg.as_string())
            await smtp.quit()
            
            return True
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {e}")
            return False
    
    async def send_welcome_email(self, to_email: str, user_name: str) -> bool:
        """Send welcome email after successful account creation"""
        html_content = self._render_template(
            'welcome.html',
            user_name=user_name,
            subject=f"Welcome to {settings.APP_NAME}!"
        )
        
        subject = f"Welcome to {settings.APP_NAME}!"
        return await self.send_email(to_email, subject, html_content)
    
    async def send_otp_email(self, to_email: str, otp_code: str, otp_type: str = "verification") -> bool:
        """Send OTP email for verification or password reset"""
        if otp_type == "password_reset":
            html_content = self._render_template(
                'reset-password.html',
                otp_code=otp_code,
                subject=f"{settings.APP_NAME} - Password Reset"
            )
            subject = f"{settings.APP_NAME} - Password Reset OTP"
        else:
            html_content = self._render_template(
                'account-verification.html',
                otp_code=otp_code,
                subject=f"{settings.APP_NAME} - Verification OTP"
            )
            subject = f"{settings.APP_NAME} - Verification OTP"
        
        return await self.send_email(to_email, subject, html_content)
    
    async def send_verification_success_email(self, to_email: str, user_name: str) -> bool:
        """Send email when account is successfully verified"""
        html_content = self._render_template(
            'welcome.html',  # Reuse welcome template or create a new one
            user_name=user_name,
            subject=f"{settings.APP_NAME} - Account Verified Successfully!"
        )
        
        subject = f"{settings.APP_NAME} - Account Verified Successfully!"
        return await self.send_email(to_email, subject, html_content)