# OTP Functionality Documentation

## Overview

The BigFarma Backend includes a comprehensive OTP (One-Time Password) system for user authentication and password reset functionality. The system is designed to be secure, user-friendly, and follows best practices.

## Features

### 1. Request OTP Endpoint
- **Endpoint**: `POST /api/v1/auth/request-otp`
- **Purpose**: Send OTP for email verification (only for existing users)
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "otp_type": "email"
  }
  ```
- **Response**:
  ```json
  {
    "message": "OTP sent successfully",
    "otp_type": "email"
  }
  ```

### 2. Forgot Password Endpoint
- **Endpoint**: `POST /api/v1/auth/forgot-password`
- **Purpose**: Send OTP for password reset (only for existing users)
- **Request Body**:
  ```json
  {
    "email": "user@example.com"
  }
  ```
- **Response**:
  ```json
  {
    "message": "Password reset OTP sent successfully",
    "otp_type": "password_reset"
  }
  ```

### 3. Verify OTP Endpoint
- **Endpoint**: `POST /api/v1/auth/verify-otp`
- **Purpose**: Verify OTP code for email verification
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "otp_code": "123456",
    "otp_type": "email"
  }
  ```

### 4. Reset Password Endpoint
- **Endpoint**: `POST /api/v1/auth/reset-password`
- **Purpose**: Reset password using OTP verification
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "otp_code": "123456",
    "new_password": "newpassword123"
  }
  ```

## Security Features

### 1. User Existence Check
- OTP is only sent to existing users
- Non-existent users receive a "User not found" error
- This prevents email enumeration attacks

### 2. Rate Limiting
- Users can only request OTP once per minute
- Prevents spam and abuse

### 3. OTP Expiration
- OTP codes expire after 10 minutes
- Expired OTPs cannot be used

### 4. Single Use
- Each OTP can only be used once
- Used OTPs are marked as `is_used = True`

### 5. Different OTP Types
- `email`: For email verification
- `password_reset`: For password reset
- `phone`: For phone verification (future implementation)

## Email Templates

### Email Verification OTP
- Subject: "BigFarma - Email Verification OTP"
- Blue-colored OTP code
- Standard verification message

### Password Reset OTP
- Subject: "BigFarma - Password Reset OTP"
- Red-colored OTP code
- Security-focused message

## Database Schema

### OTP Table
```sql
CREATE TABLE otps (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    otp_code VARCHAR NOT NULL,
    otp_type VARCHAR NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## Configuration

### Environment Variables
```env
# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Environment
ENVIRONMENT=development  # Shows OTP codes in response for testing
```

## Development vs Production

### Development Mode
- OTP codes are returned in the API response for testing
- Useful for development and testing

### Production Mode
- OTP codes are only sent via email
- No OTP codes in API responses for security

## Testing

Run the OTP tests:
```bash
pytest tests/test_otp.py -v
```

## Usage Examples

### 1. Request Email Verification OTP
```bash
curl -X POST "http://localhost:8000/api/v1/auth/request-otp" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "otp_type": "email"
  }'
```

### 2. Request Password Reset OTP
```bash
curl -X POST "http://localhost:8000/api/v1/auth/forgot-password" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com"
  }'
```

### 3. Verify OTP
```bash
curl -X POST "http://localhost:8000/api/v1/auth/verify-otp" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "otp_code": "123456",
    "otp_type": "email"
  }'
```

### 4. Reset Password
```bash
curl -X POST "http://localhost:8000/api/v1/auth/reset-password" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "otp_code": "123456",
    "new_password": "newpassword123"
  }'
```

## Important Notes

1. **Registration**: OTP is NOT sent automatically during user registration
2. **User Verification**: Only email verification OTPs mark users as verified
3. **Password Reset**: Password reset OTPs do not mark users as verified
4. **Security**: Always use HTTPS in production
5. **Email Service**: Configure SMTP settings for email delivery

## Error Handling

Common error responses:
- `404`: User not found
- `400`: Invalid OTP code, expired OTP, or rate limit exceeded
- `500`: Internal server error

## Future Enhancements

1. SMS OTP support
2. OTP resend functionality
3. Advanced rate limiting
4. OTP delivery status tracking
5. Multi-factor authentication support 