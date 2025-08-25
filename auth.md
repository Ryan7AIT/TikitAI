****# 🔐 Authentication System Documentation

## Table of Contents
- [Overview](#overview)
- [Architecture Choice](#architecture-choice)
- [Token Types](#token-types)
- [Security Features](#security-features)
- [Backend Implementation](#backend-implementation)
- [Frontend Implementation](#frontend-implementation)
- [API Endpoints](#api-endpoints)
- [Database Schema](#database-schema)
- [Common Issues & Solutions](#common-issues--solutions)
- [Development Guidelines](#development-guidelines)

## Overview

Our RAG application uses a **JWT-based dual-token authentication system** with:
- **Access Tokens**: Short-lived (15 minutes) for API authorization
- **Refresh Tokens**: Long-lived (30 days) for seamless token renewal

This provides a balance between security and user experience, following OAuth2 best practices.

## Architecture Choice

### Why Dual-Token System?

| **Single Token Approach**         | **Dual-Token Approach** ✅              |
| --------------------------------- | -------------------------------------- |
| ❌ Long expiration = security risk | ✅ Short access token limits exposure   |
| ❌ Short expiration = poor UX      | ✅ Long refresh token maintains session |
| ❌ Hard to revoke tokens           | ✅ Easy server-side revocation          |
| ❌ All-or-nothing security         | ✅ Layered security approach            |

### Why JWT + Database Hybrid?

- **Access Tokens (JWT)**: Stateless, fast verification, self-contained
- **Refresh Tokens (Database)**: Stateful, revocable, server-controlled

## Token Types

### 🎟️ Access Token (JWT)
```json
{
  "sub": "123",           // User ID
  "exp": 1693123456,      // Expiration timestamp
  "type": "access",       // Token type
  "iat": 1693122456       // Issued at
}
```

**Properties:**
- ⏱️ **Lifespan**: 15 minutes
- 💾 **Storage**: Frontend localStorage
- 🔒 **Verification**: JWT signature (stateless)
- 📍 **Usage**: Authorization header for API calls
- ⚠️ **Revocation**: Not possible (expires quickly)

### 🔐 Refresh Token (Random String)
```
Example: "xK9mP2vR8nQ7wE3tY6uI1oP5aS8dF2gH"
```

**Properties:**
- ⏱️ **Lifespan**: 30 days
- 💾 **Storage**: HTTP-only cookie (secure)
- 🔒 **Verification**: Database lookup + hash comparison
- 📍 **Usage**: Automatic renewal of access tokens
- ✅ **Revocation**: Instant (mark as inactive in DB)

## Security Features

### 🛡️ Protection Against Common Attacks

| **Attack Type**                       | **Protection**                    |
| ------------------------------------- | --------------------------------- |
| **XSS (Cross-Site Scripting)**        | Refresh token in HTTP-only cookie |
| **CSRF (Cross-Site Request Forgery)** | SameSite=strict cookie policy     |
| **Token Replay**                      | Token rotation on refresh         |
| **Session Hijacking**                 | Short access token lifespan       |
| **Brute Force**                       | Bcrypt password hashing           |

### 🔄 Token Rotation
- Each refresh generates a **new token pair**
- Old refresh tokens are **immediately invalidated**
- Prevents replay attacks with stolen refresh tokens

### 🚪 Multi-Device Logout
- Server tracks all user refresh tokens
- "Logout from all devices" invalidates all user tokens
- Useful for security incidents or device loss

## Backend Implementation

### Core Files Structure
```
auth.py                 # Core authentication functions
routers/auth_router.py  # FastAPI endpoints
models.py              # Database models
config/settings.py     # JWT configuration
```

### Key Functions

#### 🔑 Password Management
```python
def hash_password(password: str) -> str:
    """Hash password using bcrypt (slow, secure)"""
    
def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash"""
```

#### 🎫 Token Creation
```python
def create_access_token(user_id: int) -> str:
    """Create JWT access token (15min expiry)"""
    
def create_refresh_token(user_id: int, session: Session) -> str:
    """Create refresh token, store hash in DB (30day expiry)"""
    
def create_token_pair(user_id: int, session: Session) -> Tuple[str, str]:
    """Create both tokens together"""
```

#### ✅ Token Verification
```python
def verify_refresh_token(token: str, session: Session) -> Optional[User]:
    """Verify refresh token against database"""
    
def get_current_user(credentials: HTTPAuthorizationCredentials, session: Session) -> User:
    """Extract user from JWT access token"""
```

#### 🗑️ Token Invalidation
```python
def invalidate_refresh_token(token: str, session: Session) -> bool:
    """Invalidate single refresh token"""
    
def invalidate_all_user_tokens(user_id: int, session: Session) -> None:
    """Invalidate all user's refresh tokens (logout all devices)"""
```

## Frontend Implementation

### 🎯 Best Practices

#### ✅ Secure Token Storage
```javascript
// ✅ CORRECT
localStorage.setItem('access_token', data.access_token);
// Refresh token automatically stored in HTTP-only cookie

// ❌ WRONG - Never do this
localStorage.setItem('refresh_token', data.refresh_token);
```

#### 🔄 Automatic Token Refresh
```javascript
class AuthManager {
    async makeAuthenticatedRequest(url, options = {}) {
        let accessToken = localStorage.getItem('access_token');
        
        // Try request with current token
        let response = await fetch(url, {
            ...options,
            credentials: 'include', // Essential for cookies
            headers: {
                ...options.headers,
                'Authorization': `Bearer ${accessToken}`
            }
        });
        
        // If 401, refresh and retry
        if (response.status === 401) {
            const refreshed = await this.refreshToken();
            if (refreshed) {
                accessToken = localStorage.getItem('access_token');
                response = await fetch(url, {
                    ...options,
                    credentials: 'include',
                    headers: {
                        ...options.headers,
                        'Authorization': `Bearer ${accessToken}`
                    }
                });
            } else {
                this.logout();
                window.location.href = '/login';
            }
        }
        
        return response;
    }
    
    async refreshToken() {
        try {
            const response = await fetch('/auth/refresh', {
                method: 'POST',
                credentials: 'include' // Sends refresh token cookie
            });
            
            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('access_token', data.access_token);
                return true;
            }
        } catch (error) {
            console.error('Token refresh failed:', error);
        }
        return false;
    }
}
```

#### 🚀 Usage in Components
```javascript
// Use AuthManager for all API calls
const authManager = new AuthManager();

// Instead of direct fetch
const response = await authManager.makeAuthenticatedRequest('/api/documents');
const data = await response.json();
```

## API Endpoints

### 🔐 Authentication Routes

#### POST `/auth/login`
**Purpose**: Authenticate user and issue token pair

**Request:**
```json
{
  "username": "admin",
  "password": "password123"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "xK9mP2vR8nQ7wE3tY6uI...",
  "token_type": "bearer"
}
```

**Side Effects:**
- Sets `refresh_token` HTTP-only cookie
- Invalidates previous refresh tokens

#### POST `/auth/refresh`
**Purpose**: Get new token pair using refresh token

**Request:** Empty body (uses cookie)

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "newTokenXYZ123...",
  "token_type": "bearer"
}
```

**Side Effects:**
- Updates `refresh_token` HTTP-only cookie
- Invalidates old refresh token

#### POST `/auth/logout`
**Purpose**: Logout from current device

**Headers:** `Authorization: Bearer <access_token>`

**Response:**
```json
{
  "message": "Successfully logged out"
}
```

**Side Effects:**
- Invalidates current refresh token
- Clears refresh token cookie

#### POST `/auth/logout-all`
**Purpose**: Logout from all devices

**Headers:** `Authorization: Bearer <access_token>`

**Response:**
```json
{
  "message": "Successfully logged out from all devices"
}
```

**Side Effects:**
- Invalidates ALL user's refresh tokens
- Clears refresh token cookie

## Database Schema

### 👤 User Model
```python
class User(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### 🎫 RefreshToken Model
```python
class RefreshToken(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    token_hash: str = Field(index=True)  # SHA-256 hash of actual token
    expires_at: datetime
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### 🔍 Database Queries
```sql
-- Find valid refresh token
SELECT * FROM refreshtoken 
WHERE token_hash = 'hash_value' 
  AND is_active = true 
  AND expires_at > NOW();

-- Invalidate user's tokens (logout all)
UPDATE refreshtoken 
SET is_active = false 
WHERE user_id = 123 AND is_active = true;
```

## Common Issues & Solutions

### 🐛 Issue: "Getting logged out after 15 minutes"
**Cause**: Frontend not implementing automatic token refresh

**Solution**: Implement `makeAuthenticatedRequest()` method that handles 401 responses

### 🐛 Issue: "Refresh token not found"
**Cause**: Missing `credentials: 'include'` in fetch requests

**Solution**: Always include `credentials: 'include'` for cookie handling

### 🐛 Issue: "CORS errors with cookies"
**Cause**: Backend CORS not configured for credentials

**Solution**: 
```python
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,  # Essential for cookies
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"]
)
```

### 🐛 Issue: "Tokens work in Postman but not browser"
**Cause**: Different cookie handling between tools

**Solution**: Test with browser dev tools, not just API clients

## Development Guidelines

### 🎯 For Backend Developers

1. **Never expose refresh tokens in logs**
2. **Always hash refresh tokens before database storage**
3. **Use dependency injection for authentication**
4. **Set secure cookie flags in production**

```python
# ✅ Good
@router.get("/protected")
def protected_route(current_user: User = Depends(get_current_user)):
    return {"user": current_user.username}

# ❌ Bad - manual token handling
@router.get("/protected")  
def protected_route(authorization: str = Header(...)):
    # Manual JWT parsing - error prone
```

### 🎯 For Frontend Developers

1. **Never store refresh tokens in JavaScript**
2. **Always use AuthManager for API calls**
3. **Handle 401 responses gracefully**
4. **Include credentials in all requests**

```javascript
// ✅ Good
const response = await authManager.makeAuthenticatedRequest('/api/data');

// ❌ Bad - direct fetch without refresh handling
const response = await fetch('/api/data', {
    headers: { 'Authorization': `Bearer ${token}` }
});
```

### 🔧 Environment Configuration

```env
# Development
SECRET_KEY=your-development-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# Production
SECRET_KEY=your-super-secure-production-key
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7  # Shorter for production
```

### 🧪 Testing Authentication

```python
# Test user creation
def test_create_user():
    user = User(username="test", hashed_password=hash_password("test123"))
    # ...

# Test token creation
def test_token_pair():
    access_token, refresh_token = create_token_pair(user.id, session)
    assert verify_refresh_token(refresh_token, session) == user

# Test authentication flow
def test_login_flow():
    response = client.post("/auth/login", json={"username": "test", "password": "test123"})
    assert response.status_code == 200
    assert "access_token" in response.json()
```

### 📊 Monitoring & Logging

Track these metrics:
- Failed login attempts
- Token refresh frequency
- Active sessions per user
- Token expiration events

```python
# Example logging
logger.info(f"User {user.username} logged in successfully")
logger.warning(f"Failed login attempt for username: {username}")
logger.info(f"Token refreshed for user {user.id}")
```

---

## 🚀 Quick Start for New Developers

1. **Backend**: Understand `auth.py` and `auth_router.py`
2. **Frontend**: Implement `AuthManager` class
3. **Testing**: Use `/auth/login` to get tokens
4. **Debugging**: Check browser cookies and localStorage
5. **Production**: Set secure cookie flags and strong secrets

For questions, check the FastAPI docs at `/docs` endpoint or review this documentation.
