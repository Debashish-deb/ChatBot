# app/services/auth_service.py
"""
Authentication Service - Production-Ready Implementation
Supports API Keys, JWT tokens, and OAuth2
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import secrets
import hashlib
from app.config import settings
from app.models.database import User, APIKey
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

class AuthService:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.SECRET_KEY = settings.SECRET_KEY
        self.ALGORITHM = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
    
    def hash_password(self, password: str) -> str:
        """Hash a password for storing"""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a stored password against one provided by user"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def create_api_key(self, user_id: str, name: str = "default") -> tuple[str, str]:
        """
        Generate API key for user
        Returns: (plaintext_key, hashed_key)
        """
        # Generate key with prefix for identification
        prefix = "mcp_"
        key_bytes = secrets.token_urlsafe(32)
        plaintext_key = f"{prefix}{key_bytes}"
        
        # Hash the key for storage (like passwords)
        hashed_key = hashlib.sha256(plaintext_key.encode()).hexdigest()
        
        return plaintext_key, hashed_key
    
    def create_access_token(
        self, 
        data: dict, 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt
    
    def create_refresh_token(self, data: dict) -> str:
        """Create JWT refresh token (longer expiration)"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=30)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> dict:
        """
        Verify JWT token and return payload
        Raises HTTPException if invalid
        """
        try:
            payload = jwt.decode(
                token, 
                self.SECRET_KEY, 
                algorithms=[self.ALGORITHM]
            )
            
            # Check token type
            if payload.get("type") != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )
            
            return payload
            
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Could not validate credentials: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    async def verify_api_key(
        self, 
        api_key: str, 
        db: AsyncSession
    ) -> User:
        """
        Verify API key and return user
        Raises HTTPException if invalid
        """
        # Hash the provided key
        hashed_key = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Look up in database
        result = await db.execute(
            select(APIKey).where(
                APIKey.key_hash == hashed_key,
                APIKey.is_active == True
            )
        )
        api_key_obj = result.scalar_one_or_none()
        
        if not api_key_obj:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        # Check if expired
        if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key expired"
            )
        
        # Update last used timestamp
        api_key_obj.last_used_at = datetime.utcnow()
        await db.commit()
        
        # Get user
        result = await db.execute(
            select(User).where(User.id == api_key_obj.user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        return user
    
    async def get_user_by_email(
        self, 
        email: str, 
        db: AsyncSession
    ) -> Optional[User]:
        """Get user by email"""
        result = await db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def authenticate_user(
        self, 
        email: str, 
        password: str, 
        db: AsyncSession
    ) -> Optional[User]:
        """Authenticate user with email and password"""
        user = await self.get_user_by_email(email, db)
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user

# Global instance
auth_service = AuthService()
