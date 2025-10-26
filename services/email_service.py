import logging
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import os
import asyncio

from config import settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.templates_dir = Path(__file__).parent.parent / "templates" / "emails"
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=True
        )
        # SMTP configuration with timeouts
        self.smtp_timeout = 10  # seconds for serverless
    
    def _render_template(self, template_name: str, **context) -> str:
        """Render HTML template with given context"""
        try:
            template_path = self.templates_dir / template_name
            if not template_path.exists():
                logger.warning(f"Template not found: {template_name}, using fallback")
                return self._create_fallback_email(**context)
            
            template = self.jinja_env.get_template(template_name)
            default_context = {
                'app_name': settings.APP_NAME,
                'expire_minutes': settings.OTP_EXPIRE_MINUTES
            }
            default_context.update(context)
            
            return template.render(**default_context)
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {e}")
            return self._create_fallback_email(**context)
    
    def _create_fallback_email(self, **context) -> str:
        """Create fallback email content if template rendering fails"""
        # Your existing fallback code is fine
        # ... keep your existing _create_fallback_email method ...
    
    async def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send email with HTML content - SERVERLESS FRIENDLY"""
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning("SMTP credentials not configured.")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = settings.SMTP_USER
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(html_content, 'html'))
            
            # ✅ SERVERLESS FIX: Configure timeouts
            smtp = aiosmtplib.SMTP(
                hostname=settings.SMTP_HOST, 
                port=settings.SMTP_PORT,
                timeout=self.smtp_timeout,
                use_tls=settings.SMTP_USE_TLS  # Let aiosmtplib handle TLS properly
            )
            
            # ✅ SERVERLESS FIX: Use a single connection with timeout
            await asyncio.wait_for(
                self._send_smtp_message(smtp, msg, to_email),
                timeout=self.smtp_timeout
            )
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except asyncio.TimeoutError:
            logger.error(f"SMTP timeout sending email to {to_email}")
            return False
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {e}")
            return False
    
    async def _send_smtp_message(self, smtp, msg, to_email):
        """Helper method to send SMTP message with proper cleanup"""
        try:
            await smtp.connect()
            
            # Login and send
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            await smtp.send_message(msg)
            
        finally:
            # Always try to quit gracefully
            try:
                await smtp.quit()
            except:
                pass  # Ignore quit errors in serverless
    
    # ✅ SERVERLESS FIX: Alternative synchronous method for better reliability
    async def send_email_sync_fallback(self, to_email: str, subject: str, html_content: str) -> bool:
        """Synchronous fallback for serverless environments"""
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            
            msg = MIMEMultipart()
            msg['From'] = settings.SMTP_USER
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(html_content, 'html'))
            
            # Use synchronous SMTP with timeout
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=8) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Email sent via sync method to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Sync email failed to {to_email}: {e}")
            return False
    
    async def send_otp_email(self, to_email: str, otp_code: str, otp_type: str = "verification") -> bool:
        """Send OTP email with serverless-friendly approach"""
        # Try async first, then fallback to sync
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
        
        success = await self.send_email(to_email, subject, html_content)
        
        if not success:
            logger.info("Async email failed, trying sync fallback")
            success = await self.send_email_sync_fallback(to_email, subject, html_content)
        
        return success
    
    async def send_welcome_email(self, to_email: str, user_name: str) -> bool:
        html_content = self._render_template(
            'welcome.html',
            user_name=user_name
        )
        subject = f"Welcome to {settings.APP_NAME}!"
        return await self.send_email(to_email, subject, html_content)
    
    async def send_verification_success_email(self, to_email: str, user_name: str) -> bool:
        html_content = self._render_template(
            'verification.html', 
            user_name=user_name
        )
        subject = f"{settings.APP_NAME} - Account Verified Successfully!"
        return await self.send_email(to_email, subject, html_content)
