# BigFarma Backend API

A production-ready FastAPI backend for BigFarma with Supabase integration, featuring comprehensive authentication, user management, and OTP verification.

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
- **Supabase** - Backend-as-a-Service with PostgreSQL
- **SQLAlchemy** - SQL toolkit and ORM
- **Pydantic** - Data validation using Python type annotations
- **JWT** - JSON Web Tokens for authentication
- **Passlib** - Password hashing library
- **Uvicorn** - ASGI server for running FastAPI

## Project Structure

```
bigfarma/
├── .env.example              # Environment variables template
├── .gitignore               # Git ignore rules
├── requirements.txt         # Python dependencies
├── pyproject.toml          # Project configuration
├── README.md              # This file
├── src/                   # Source code
│   ├── __init__.py
│   ├── main.py           # FastAPI application entry point
│   ├── config/           # Configuration management
│   │   ├── __init__.py
│   │   ├── config.py     # Settings and environment variables
│   │   └── logging.py    # Logging configuration
│   ├── models/           # Database models
│   │   ├── __init__.py
│   │   └── accounts.py   # User, OTP, Profile models
│   ├── schemas/          # Pydantic schemas
│   │   ├── __init__.py
│   │   └── accounts.py   # Request/Response models
│   ├── services/         # Business logic
│   │   ├── __init__.py
│   │   └── auth.py       # Authentication service
│   ├── api/              # API routes
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── api.py    # Main API router
│   │       ├── dependencies.py  # API dependencies
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           └── auth.py      # Authentication endpoints
│   ├── database.py       # Database connection and setup
│   └── utils/            # Utilities
│       ├── __init__.py
│       ├── security.py   # Security utilities
│       └── exceptions.py # Custom exceptions
└── tests/                # Test files
    ├── __init__.py
    └── test_auth.py      # Authentication tests
```

## Quick Start

### Prerequisites

- Python 3.9 or higher
- Supabase account and project
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

5. **Configure Supabase**
   - Create a new Supabase project
   - Get your project URL and API keys
   - Update the `.env` file with your Supabase credentials

6. **Run the application**
   ```bash
   python -m src.main
   ```

The API will be available at `http://localhost:8000`

### Environment Variables

Create a `.env` file with the following variables:

```env
# Environment
ENVIRONMENT=development
DEBUG=true

# Database (Supabase)
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key

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
| POST | `/api/v1/auth/request-otp` | Request OTP for verification |
| POST | `/api/v1/auth/verify-otp` | Verify OTP |
| POST | `/api/v1/auth/reset-password` | Reset password using OTP |
| GET | `/api/v1/auth/me` | Get current user info |
| PUT | `/api/v1/auth/me` | Update current user |
| POST | `/api/v1/auth/me/profile` | Create user profile |
| PUT | `/api/v1/auth/me/profile` | Update user profile |
| POST | `/api/v1/auth/change-password` | Change password |

### Example Usage

#### Register a new user
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "user@example.com",
       "password": "securepassword123",
       "phone": "+1234567890"
     }'
```

#### Login
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "user@example.com",
       "password": "securepassword123"
     }'
```

#### Get current user (with authentication)
```bash
curl -X GET "http://localhost:8000/api/v1/auth/me" \
     -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_auth.py
```

### Code Quality

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

### Database Setup

The application uses Supabase as the backend. You'll need to:

1. Create tables in your Supabase project
2. Set up Row Level Security (RLS) policies
3. Configure authentication settings

Example SQL for creating tables:

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR UNIQUE NOT NULL,
    phone VARCHAR UNIQUE,
    password_hash VARCHAR NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- OTP table
CREATE TABLE otps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    otp_code VARCHAR NOT NULL,
    otp_type VARCHAR NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Profiles table
CREATE TABLE profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    first_name VARCHAR,
    last_name VARCHAR,
    avatar_url VARCHAR,
    bio TEXT,
    date_of_birth DATE,
    gender VARCHAR,
    address TEXT,
    city VARCHAR,
    state VARCHAR,
    country VARCHAR,
    postal_code VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Deployment

### Production Considerations

1. **Environment Variables**: Set `ENVIRONMENT=production` and `DEBUG=false`
2. **Secret Key**: Use a strong, unique secret key
3. **CORS**: Configure `ALLOWED_HOSTS` with your domain
4. **Database**: Use production Supabase instance
5. **Logging**: Configure proper log aggregation
6. **HTTPS**: Use HTTPS in production

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

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