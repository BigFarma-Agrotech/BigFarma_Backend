import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

from app.main import app
from app.database import Base, get_db_session
from app.services.auth import auth_service

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db_session] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    """Setup test database before each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def test_user():
    """Create a test user."""
    user_data = {
        "email": "test@example.com",
        "password": "testpassword123",
        "phone": "1234567890"
    }
    response = client.post("/api/v1/auth/register", json=user_data)
    return user_data

class TestOTPFunctionality:
    """Test OTP functionality for request OTP and forgot password."""
    
    @patch('app.services.auth.AuthService.send_otp_email')
    def test_request_otp_success(self, mock_send_email, test_user):
        """Test successful OTP request for existing user."""
        # Mock the email sending
        mock_send_email.return_value = None
        
        otp_data = {
            "email": "test@example.com",
            "otp_type": "email"
        }
        
        response = client.post("/api/v1/auth/request-otp", json=otp_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "OTP sent successfully"
        assert data["otp_type"] == "email"
        
        # Verify email was called
        mock_send_email.assert_called_once()
    
    def test_request_otp_user_not_found(self):
        """Test OTP request for non-existent user."""
        otp_data = {
            "email": "nonexistent@example.com",
            "otp_type": "email"
        }
        
        response = client.post("/api/v1/auth/request-otp", json=otp_data)
        
        assert response.status_code == 404
        data = response.json()
        assert "User not found" in data["detail"]
    
    @patch('app.services.auth.AuthService.send_otp_email')
    def test_forgot_password_success(self, mock_send_email, test_user):
        """Test successful forgot password OTP request."""
        # Mock the email sending
        mock_send_email.return_value = None
        
        forgot_data = {
            "email": "test@example.com"
        }
        
        response = client.post("/api/v1/auth/forgot-password", json=forgot_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Password reset OTP sent successfully"
        assert data["otp_type"] == "password_reset"
        
        # Verify email was called
        mock_send_email.assert_called_once()
    
    def test_forgot_password_user_not_found(self):
        """Test forgot password for non-existent user."""
        forgot_data = {
            "email": "nonexistent@example.com"
        }
        
        response = client.post("/api/v1/auth/forgot-password", json=forgot_data)
        
        assert response.status_code == 404
        data = response.json()
        assert "User not found" in data["detail"]
    
    @patch('app.services.auth.AuthService.send_otp_email')
    def test_verify_otp_success(self, mock_send_email, test_user):
        """Test successful OTP verification."""
        # Mock the email sending
        mock_send_email.return_value = None
        
        # First request OTP
        otp_data = {
            "email": "test@example.com",
            "otp_type": "email"
        }
        
        response = client.post("/api/v1/auth/request-otp", json=otp_data)
        assert response.status_code == 200
        
        # Get the OTP code from the response (in development mode)
        otp_response = response.json()
        otp_code = otp_response["message"].split("Code: ")[1]
        
        # Verify OTP
        verify_data = {
            "email": "test@example.com",
            "otp_code": otp_code,
            "otp_type": "email"
        }
        
        response = client.post("/api/v1/auth/verify-otp", json=verify_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "OTP verified successfully"
    
    def test_verify_otp_invalid_code(self, test_user):
        """Test OTP verification with invalid code."""
        verify_data = {
            "email": "test@example.com",
            "otp_code": "000000",
            "otp_type": "email"
        }
        
        response = client.post("/api/v1/auth/verify-otp", json=verify_data)
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid OTP code" in data["detail"]
    
    @patch('app.services.auth.AuthService.send_otp_email')
    def test_reset_password_success(self, mock_send_email, test_user):
        """Test successful password reset."""
        # Mock the email sending
        mock_send_email.return_value = None
        
        # First request password reset OTP
        forgot_data = {
            "email": "test@example.com"
        }
        
        response = client.post("/api/v1/auth/forgot-password", json=forgot_data)
        assert response.status_code == 200
        
        # Get the OTP code from the response (in development mode)
        otp_response = response.json()
        otp_code = otp_response["message"].split("Code: ")[1]
        
        # Reset password
        reset_data = {
            "email": "test@example.com",
            "otp_code": otp_code,
            "new_password": "newpassword123"
        }
        
        response = client.post("/api/v1/auth/reset-password", json=reset_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Password reset successfully"
    
    def test_registration_no_otp_sent(self):
        """Test that registration doesn't send OTP automatically."""
        with patch('app.services.auth.AuthService.send_otp_email') as mock_send_email:
            user_data = {
                "email": "newuser@example.com",
                "password": "newpassword123",
                "phone": "9876543210"
            }
            
            response = client.post("/api/v1/auth/register", json=user_data)
            
            assert response.status_code == 201
            # Verify that no OTP email was sent during registration
            mock_send_email.assert_not_called()
    
    def test_rate_limiting_otp_requests(self, test_user):
        """Test rate limiting for OTP requests."""
        with patch('app.services.auth.AuthService.send_otp_email') as mock_send_email:
            mock_send_email.return_value = None
            
            otp_data = {
                "email": "test@example.com",
                "otp_type": "email"
            }
            
            # First request should succeed
            response = client.post("/api/v1/auth/request-otp", json=otp_data)
            assert response.status_code == 200
            
            # Second request within 1 minute should fail
            response = client.post("/api/v1/auth/request-otp", json=otp_data)
            assert response.status_code == 400
            data = response.json()
            assert "Please wait at least 1 minute" in data["detail"] 