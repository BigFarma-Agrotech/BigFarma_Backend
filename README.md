# BigFarma Backend API

A production-ready FastAPI backend for BigFarma with comprehensive authentication, user management, and OTP verification system.

## Features

- 🔐 **JWT Authentication** - Secure token-based authentication
- 👤 **User Management** - Complete user registration, login, and profile management
- 📧 **OTP Verification** - Email and phone verification with OTP
- 🛡️ **Security** - Password hashing, input validation, and CORS protection
- 📊 **Structured Logging** - Comprehensive logging with rotation
- 🧪 **Testing** - Unit and integration tests with pytest
- 📚 **API Documentation** - Auto-generated OpenAPI/Swagger documentation
- 🚀 **Production Ready** - Environment-based configuration and error handling

## Tech Stack

- **FastAPI** - Modern, fast web framework for building APIs
- **PostgreSQL** - Primary database with SQLAlchemy ORM
- **Pydantic** - Data validation using Python type annotations
- **JWT** - JSON Web Tokens for authentication
- **Passlib** - Password hashing library
- **Uvicorn** - ASGI server for running FastAPI

## Quick Start

### Prerequisites

- Python 3.9 or higher
- PostgreSQL database
- Virtual environment (recommended)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd bigfarma
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase credentials and other settings
   ```

5. **Configure Database**
   - Set up PostgreSQL database
   - Update the `.env` file with your database credentials

6. **Run the application**
   ```bash
    uvicorn app.main:app --reload
   ```

The API will be available at `http://localhost:8000`

### Environment Variables

Create a `.env` file with the following variables:

```env
# Environment
ENVIRONMENT=development
DEBUG=true

# Database (PostgreSQL)
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your_db_host
DB_PORT=5432
DB_NAME=your_db_name

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Email (for OTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Logging
LOG_LEVEL=INFO
```

## OTP System

The application includes a comprehensive OTP (One-Time Password) system for:

- **Email Verification**: Verify user email addresses
- **Password Reset**: Secure password reset functionality
- **Rate Limiting**: Prevents abuse with 1-minute cooldown
- **Security**: 10-minute expiration, single-use codes

### Email Configuration

To enable email sending for OTPs:

1. **Gmail (Recommended)**:
   - Enable 2-Factor Authentication
   - Generate App Password at: https://myaccount.google.com/apppasswords
   - Use the 16-character App Password

2. **Alternative Providers**: Outlook, Yahoo, SendGrid

See `EMAIL_SETUP_GUIDE.md` for detailed configuration instructions.

### Development Mode

In development mode (`ENVIRONMENT=development`), OTP codes are returned in API responses for testing.

## API Documentation

Once the server is running, you can access:

- **Interactive API docs**: http://localhost:8000/docs
- **ReDoc documentation**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register a new user |
| POST | `/api/v1/auth/login` | Login user |
| POST | `/api/v1/auth/request-otp` | Request OTP for email verification |
| POST | `/api/v1/auth/verify-otp` | Verify OTP code |
| POST | `/api/v1/auth/forgot-password` | Request password reset OTP |
| POST | `/api/v1/auth/reset-password` | Reset password using OTP |
| GET | `/api/v1/auth/me` | Get current user info |
| PUT | `/api/v1/auth/me` | Update current user |
| POST | `/api/v1/auth/me/profile` | Create user profile |
| PUT | `/api/v1/auth/me/profile` | Update user profile |
| POST | `/api/v1/auth/change-password` | Change password |


## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions, please open an issue on GitHub or contact the development team. 