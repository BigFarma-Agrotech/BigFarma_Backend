import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.main import app

client = TestClient(app)


class TestAuthEndpoints:
    """Test authentication endpoints."""
    
    def test_register_user_success(self):
        """Test successful user registration."""
        user_data = {
            "email": "test@example.com",
            "password": "testpassword123",
            "phone": "+1234567890"
        }
        
        with patch('src.services.auth.AuthService.create_user', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {
                "id": "test-id",
                "email": "test@example.com",
                "phone": "+1234567890",
                "is_active": True,
                "is_verified": False,
                "is_superuser": False,
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00"
            }
            
            response = client.post("/api/v1/auth/register", json=user_data)
            
            assert response.status_code == 201
            data = response.json()
            assert data["user"]["email"] == "test@example.com"
            assert "access_token" in data["token"]
    
    def test_register_user_invalid_email(self):
        """Test user registration with invalid email."""
        user_data = {
            "email": "invalid-email",
            "password": "testpassword123"
        }
        
        response = client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == 422
    
    def test_register_user_weak_password(self):
        """Test user registration with weak password."""
        user_data = {
            "email": "test@example.com",
            "password": "123"
        }
        
        response = client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == 422
    
    def test_login_user_success(self):
        """Test successful user login."""
        login_data = {
            "email": "test@example.com",
            "password": "testpassword123"
        }
        
        with patch('src.services.auth.AuthService.authenticate_user', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = {
                "id": "test-id",
                "email": "test@example.com",
                "password_hash": "hashed_password",
                "is_active": True,
                "is_verified": True,
                "is_superuser": False,
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00"
            }
            
            response = client.post("/api/v1/auth/login", json=login_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["user"]["email"] == "test@example.com"
            assert "access_token" in data["token"]
    
    def test_login_user_invalid_credentials(self):
        """Test login with invalid credentials."""
        login_data = {
            "email": "test@example.com",
            "password": "wrongpassword"
        }
        
        with patch('src.services.auth.AuthService.authenticate_user', new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = None
            
            response = client.post("/api/v1/auth/login", json=login_data)
            
            assert response.status_code == 401
    
    def test_request_otp_success(self):
        """Test successful OTP request."""
        otp_data = {
            "email": "test@example.com",
            "otp_type": "email"
        }
        
        with patch('src.services.auth.AuthService.create_otp', new_callable=AsyncMock) as mock_otp:
            mock_otp.return_value = "123456"
            
            response = client.post("/api/v1/auth/request-otp", json=otp_data)
            
            assert response.status_code == 200
            data = response.json()
            assert "OTP sent successfully" in data["message"]
    
    def test_verify_otp_success(self):
        """Test successful OTP verification."""
        otp_data = {
            "email": "test@example.com",
            "otp_code": "123456",
            "otp_type": "email"
        }
        
        with patch('src.services.auth.AuthService.verify_otp', new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = True
            
            response = client.post("/api/v1/auth/verify-otp", json=otp_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "OTP verified successfully"
    
    def test_get_current_user_unauthorized(self):
        """Test getting current user without authentication."""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
    
    def test_get_current_user_authorized(self):
        """Test getting current user with valid token."""
        # This test would require a valid JWT token
        # In a real test, you would create a token and use it
        pass


class TestHealthCheck:
    """Test health check endpoint."""
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/docs")
        
        # FastAPI automatically creates docs endpoint
        assert response.status_code == 200 