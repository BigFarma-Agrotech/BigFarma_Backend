import logging
import httpx
from email.utils import parseaddr
from pathlib import Path
from typing import Optional
from jinja2 import Environment, FileSystemLoader
import datetime

from config import settings

logger = logging.getLogger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"

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
        """Send email via Brevo's Transactional Emails API"""
        if not settings.BREVO_API_KEY or not settings.MAIL_FROM:
            logger.warning("Brevo API credentials not configured.")
            return False

        sender_name, sender_email = parseaddr(settings.MAIL_FROM)
        payload = {
            "sender": {"name": sender_name or settings.APP_NAME, "email": sender_email},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_content,
        }
        headers = {
            "accept": "application/json",
            "api-key": settings.BREVO_API_KEY,
            "content-type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(BREVO_SEND_URL, json=payload, headers=headers)

            if response.status_code in (200, 201):
                logger.info(f"Email sent successfully to {to_email}")
                return True

            logger.error(f"Error sending email to {to_email}: {response.status_code} {response.text}")
            return False

        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return False
    
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

    async def send_order_confirmation_email(self, to_email: str, name: str, order_number: str,
                                            product_name: str, quantity: str, total_price: float,
                                            delivery_address: str,
                                            estimated_delivery_date: Optional[datetime.datetime] = None) -> bool:
        """Send email when an order has been placed successfully"""
        html_content = self._render_template(
            'order_confirmation.html',
            name=name,
            order_number=order_number,
            product_name=product_name,
            quantity=quantity,
            total_price=f"{total_price:,.2f}",
            delivery_address=delivery_address,
            estimated_delivery=estimated_delivery_date.strftime("%d %b %Y") if estimated_delivery_date else None
        )

        subject = f"{settings.APP_NAME} - Order {order_number} Confirmed"
        return await self.send_email(to_email, subject, html_content)

    async def send_login_alert_email(self, to_email: str, name: str, login_time: datetime.datetime,
                                     ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> bool:
        """Send email whenever the account is signed in to"""
        html_content = self._render_template(
            'login_alert.html',
            name=name,
            login_time=login_time.strftime("%d %b %Y, %H:%M UTC"),
            ip_address=ip_address,
            user_agent=user_agent
        )

        subject = f"{settings.APP_NAME} - New Sign-in to Your Account"
        return await self.send_email(to_email, subject, html_content)


# Create a singleton instance for easy import
email_service = EmailService()
