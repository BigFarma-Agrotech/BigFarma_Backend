# Email Setup Guide for BigFarma Backend


## Solution Options

### Option 1: Gmail with App Password (Recommended)

1. **Enable 2-Factor Authentication**:
   - Go to [Google Account Settings](https://myaccount.google.com/)
   - Security → 2-Step Verification → Turn it ON

2. **Generate App Password**:
   - Go to [App Passwords](https://myaccount.google.com/apppasswords)
   - Select "Mail" and "Other (Custom name)"
   - Name it "BigFarma Backend"
   - Copy the 16-character password

3. **Update Environment Variables**:
   ```env
   SMTP_USER=your-email@gmail.com
   SMTP_PASSWORD=your-16-character-app-password
   ```

### Option 2: Gmail with Less Secure Apps (Not Recommended)

1. Go to [Google Account Settings](https://myaccount.google.com/)
2. Security → Less secure app access
3. Turn it ON
4. Use your regular Gmail password

### Option 3: Use Outlook/Hotmail

```env
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USER=your-email@outlook.com
SMTP_PASSWORD=your-password
```

### Option 4: Use Yahoo Mail

```env
SMTP_HOST=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USER=your-email@yahoo.com
SMTP_PASSWORD=your-app-password
```

### Option 5: Use SendGrid (Production Recommended)

1. Sign up for [SendGrid](https://sendgrid.com/)
2. Create an API key
3. Update configuration:

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
```

## Testing Email Configuration

### Test Script
Create a file `test_email.py`:

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

def test_email_config():
    # Get settings from environment
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not smtp_user or not smtp_password:
        print("❌ SMTP_USER or SMTP_PASSWORD not set")
        return
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = smtp_user  # Send to yourself for testing
        msg['Subject'] = "BigFarma - Email Test"
        
        body = "This is a test email from BigFarma Backend."
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        text = msg.as_string()
        server.sendmail(smtp_user, smtp_user, text)
        server.quit()
        
        print("✅ Email sent successfully!")
        print(f"Check your inbox: {smtp_user}")
        
    except Exception as e:
        print(f"❌ Email test failed: {e}")

if __name__ == "__main__":
    test_email_config()
```

### Run the Test
```bash
python test_email.py
```

## Environment File Example

Create a `.env` file in your project root:

```env
# Database Configuration
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your_db_host
DB_PORT=5432
DB_NAME=your_db_name

# Email Configuration (Gmail with App Password)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-16-character-app-password

# Environment
ENVIRONMENT=development
```

## Troubleshooting

### Common Gmail Issues

1. **"Username and Password not accepted"**:
   - Use App Password instead of regular password
   - Enable 2-Factor Authentication first

2. **"Less secure app access"**:
   - Enable this option in Google Account settings
   - Or use App Password (recommended)

3. **"Connection timeout"**:
   - Check firewall settings
   - Try different port (465 with SSL instead of 587 with TLS)

### Alternative Ports

```env
# Gmail with SSL (port 465)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
```

### Debug Mode

To see detailed SMTP logs, add this to your email sending function:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Production Recommendations

1. **Use SendGrid or similar service** for production
2. **Never use Gmail with regular password** in production
3. **Use environment variables** for all sensitive data
4. **Implement email delivery tracking**
5. **Set up email templates** for different scenarios

## Quick Fix for Development

If you just want to test the OTP functionality without email:

1. Set `ENVIRONMENT=development` in your `.env` file
2. The OTP codes will be returned in the API response
3. You can see the codes in the logs and API responses

This allows you to test the complete OTP flow without email configuration. 