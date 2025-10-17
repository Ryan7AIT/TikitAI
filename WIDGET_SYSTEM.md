# Widget System Implementation Guide

## 📋 Overview

The Widget System enables authenticated users to generate embeddable chat widgets for their websites. This allows external website visitors to interact with custom chatbots without needing to authenticate directly with the platform.

## 🎯 Key Features

1. **Bot Management**: Users can create and manage chatbots within workspaces
2. **Secure Widget Tokens**: Generate signed JWT tokens for embedding widgets
3. **Session Management**: Track visitor chat sessions separately from platform users
4. **Token Refresh**: Extend widget token validity without regeneration
5. **Access Control**: Verify bot ownership before widget generation

## 🏗️ Architecture

### Token Types

The system uses three types of tokens:

1. **Access Token** (`type: "access"`)
   - Duration: 60 minutes
   - Purpose: Platform user authentication
   - Used for: All internal API endpoints

2. **Refresh Token** (database-stored hash)
   - Duration: 30 days
   - Purpose: Renewing access tokens
   - Used for: `/auth/refresh` endpoint

3. **Widget Token** (`type: "widget"`)
   - Duration: 7 days (configurable)
   - Purpose: Widget authentication on external sites
   - Payload: `{ "type": "widget", "bot_id": 123, "owner_id": 456, "exp": ... }`
   - Used for: Widget endpoints and chat sessions

### Data Models

#### Bot Model
```python
class Bot(SQLModel, table=True):
    id: int (primary key)
    name: str
    description: Optional[str]
    workspace_id: int (foreign key -> Workspace)
    owner_id: int (foreign key -> User)
    system_prompt: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

#### WidgetToken Model
```python
class WidgetToken(SQLModel, table=True):
    id: int (primary key)
    bot_id: int (foreign key -> Bot)
    owner_id: int (foreign key -> User)
    token_hash: str (SHA256 hash)
    expires_at: datetime
    created_at: datetime
    is_active: bool
    last_used_at: Optional[datetime]
```

#### ChatSession Model
```python
class ChatSession(SQLModel, table=True):
    id: int (primary key)
    bot_id: int (foreign key -> Bot)
    session_token: str (unique identifier)
    visitor_identifier: Optional[str]
    started_at: datetime
    last_activity_at: datetime
    messages_count: int
    is_active: bool
```

## 🔐 Security Considerations

### Widget Token Security
- Tokens are signed with JWT and contain only necessary data
- Original tokens are hashed (SHA256) before database storage
- Token validation checks: signature, expiration, type, and active status
- Tokens can be revoked individually or globally per bot

### Access Control
- Only bot owners can generate widget tokens
- Bot ownership verification on every widget operation
- Workspace membership validation
- Rate limiting on widget endpoints (recommended)

### CORS Configuration
- Widget endpoints need permissive CORS for external embedding
- Restrict by origin when possible
- Validate referrer headers for additional security

## 📡 API Endpoints

### 1. Generate Widget Token
**Endpoint**: `POST /api/widget/generate`

**Authentication**: Bearer `<access_token>` (platform user)

**Request**:
```json
{
  "bot_id": 123
}
```

**Response**:
```json
{
  "widget_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2025-10-24T12:00:00Z",
  "embed_code": "<script src=\"https://myapp.com/widget.js\" data-bot-id=\"123\" data-token=\"eyJhbGc...\"></script>"
}
```

**Process**:
1. Verify user is authenticated
2. Verify bot exists and user owns it
3. Clean up expired widget tokens for this bot
4. Generate signed JWT with type="widget"
5. Hash and store token in database
6. Return token and embed code

---

### 2. Start Chat Session
**Endpoint**: `POST /api/widget/session/start`

**Authentication**: Bearer `<widget_token>`

**Request**:
```json
{
  "visitor_identifier": "optional-unique-id"
}
```

**Response**:
```json
{
  "session_id": "sess_abc123xyz",
  "bot_name": "Customer Support Bot",
  "welcome_message": "Hello! How can I help you today?"
}
```

**Process**:
1. Validate widget token (signature, expiration, type)
2. Verify bot is active
3. Create new chat session record
4. Update token's last_used_at
5. Return session details

---

### 3. Send Message (Widget)
**Endpoint**: `POST /api/widget/chat`

**Authentication**: Bearer `<widget_token>`

**Request**:
```json
{
  "session_id": "sess_abc123xyz",
  "message": "What are your business hours?"
}
```

**Response**:
```json
{
  "answer": "Our business hours are Monday-Friday 9am-5pm EST.",
  "message_id": 789,
  "latency_ms": 1234
}
```

**Process**:
1. Validate widget token
2. Verify session exists and belongs to bot
3. Process message through RAG pipeline (workspace context)
4. Store message with session_id
5. Update session last_activity_at
6. Return response

---

### 4. Refresh Widget Token
**Endpoint**: `POST /api/widget/refresh`

**Authentication**: Bearer `<expired_widget_token>`

**Request**:
```json
{
  "widget_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response**:
```json
{
  "widget_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2025-10-31T12:00:00Z"
}
```

**Process**:
1. Decode expired token (allow grace period)
2. Verify token exists in database and is active
3. Verify bot is still active
4. Generate new widget token
5. Optionally deactivate old token
6. Return new token

---

### 5. Revoke Widget Token
**Endpoint**: `POST /api/widget/revoke`

**Authentication**: Bearer `<access_token>` (platform user)

**Request**:
```json
{
  "bot_id": 123,
  "token_id": 456  // Optional, revokes specific token; if omitted, revokes all
}
```

**Response**:
```json
{
  "message": "Widget token(s) revoked successfully",
  "tokens_revoked": 1
}
```

---

## 🌐 Widget Embedding

### Embed Code Template
```html
<script src="https://myapp.com/widget.js" 
        data-bot-id="123" 
        data-token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        data-theme="light"
        data-position="bottom-right">
</script>
```

### Widget.js Functionality
The widget script should:
1. Load with DOM and inject chat UI
2. Initialize session on first load
3. Store session_id in localStorage
4. Handle token refresh automatically
5. Provide customization options (theme, position, colors)
6. Support mobile responsiveness
7. Implement lazy loading for performance

### Example Widget.js Structure
```javascript
(function() {
  const WIDGET_CONFIG = {
    botId: document.currentScript.dataset.botId,
    token: document.currentScript.dataset.token,
    apiBase: 'https://myapp.com/api/widget',
    theme: document.currentScript.dataset.theme || 'light',
    position: document.currentScript.dataset.position || 'bottom-right'
  };

  class ChatWidget {
    constructor(config) { /* ... */ }
    async startSession() { /* ... */ }
    async sendMessage(text) { /* ... */ }
    renderUI() { /* ... */ }
    handleTokenRefresh() { /* ... */ }
  }

  const widget = new ChatWidget(WIDGET_CONFIG);
  widget.init();
})();
```

---

## 📊 Monitoring & Analytics

### Metrics to Track
- Widget token generation rate
- Active sessions per bot
- Message volume per bot/session
- Average session duration
- Token refresh rate
- Token expiration/revocation events

### Database Queries
```sql
-- Active widget sessions
SELECT COUNT(*) FROM ChatSession 
WHERE bot_id = ? AND is_active = true;

-- Messages per bot (last 24h)
SELECT bot_id, COUNT(*) as msg_count
FROM Message m
JOIN ChatSession cs ON m.session_id = cs.id
WHERE m.timestamp > NOW() - INTERVAL '24 hours'
GROUP BY bot_id;

-- Widget token usage
SELECT wt.bot_id, COUNT(*) as active_tokens, MAX(last_used_at) as last_usage
FROM WidgetToken wt
WHERE wt.is_active = true AND wt.expires_at > NOW()
GROUP BY wt.bot_id;
```

---

## 🚀 Implementation Steps

### Phase 1: Database Setup
1. ✅ Create Bot model
2. ✅ Create WidgetToken model
3. ✅ Create ChatSession model
4. ✅ Update Message model to support session_id
5. ✅ Run migrations

### Phase 2: Authentication Layer
1. ✅ Add widget token utilities to auth.py
2. ✅ Create widget token validation dependency
3. ✅ Add settings for widget token expiration
4. ✅ Implement token refresh logic

### Phase 3: API Implementation
1. ✅ Create widget_router.py
2. ✅ Implement /generate endpoint
3. ✅ Implement /session/start endpoint
4. ✅ Implement /chat endpoint
5. ✅ Implement /refresh endpoint
6. ✅ Implement /revoke endpoint

### Phase 4: Widget Script
1. ✅ Create widget.js client library
2. ✅ Implement session management
3. ✅ Implement chat UI
4. ✅ Add token refresh handling
5. ✅ Add customization options

### Phase 5: Testing & Documentation
1. Test widget token generation
2. Test session lifecycle
3. Test token refresh
4. Test token revocation
5. Load testing for widget endpoints
6. Update API documentation

---

## 🔧 Configuration

### Environment Variables
```env
# Widget Configuration
WIDGET_TOKEN_EXPIRE_DAYS=7
WIDGET_SESSION_TIMEOUT_MINUTES=30
WIDGET_MAX_SESSIONS_PER_BOT=1000
WIDGET_RATE_LIMIT_PER_MINUTE=60

# CORS for Widget Endpoints
WIDGET_ALLOWED_ORIGINS=*  # Use specific origins in production
```

### Settings.py Addition
```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Widget Configuration
    widget_token_expire_days: int = 7
    widget_session_timeout_minutes: int = 30
    widget_max_sessions_per_bot: int = 1000
    widget_allowed_origins: str = "*"  # Comma-separated list
```

---

## 🐛 Error Handling

### Common Errors

| Error Code | Description          | Solution                    |
| ---------- | -------------------- | --------------------------- |
| 401        | Invalid widget token | Refresh token or regenerate |
| 403        | Bot access denied    | Verify bot ownership        |
| 404        | Bot not found        | Check bot_id is correct     |
| 410        | Token expired        | Use refresh endpoint        |
| 429        | Rate limit exceeded  | Implement backoff strategy  |
| 503        | Bot inactive         | Contact bot owner           |

### Error Response Format
```json
{
  "detail": "Widget token has expired",
  "error_code": "TOKEN_EXPIRED",
  "expires_at": "2025-10-17T12:00:00Z",
  "refresh_available": true
}
```

---

## 📝 Best Practices

### For Platform Users
1. Regularly rotate widget tokens (every 30 days)
2. Monitor widget usage analytics
3. Set appropriate bot system prompts
4. Test widgets in staging before production
5. Implement fallback messages for errors

### For Developers
1. Always validate widget tokens on every request
2. Implement rate limiting on widget endpoints
3. Log widget activity for analytics
4. Clean up expired sessions regularly
5. Use HTTPS only for widget embedding
6. Implement CORS carefully
7. Monitor token refresh patterns
8. Set up alerts for high failure rates

### For Widget Embedders
1. Use latest widget.js version
2. Implement error handling on client side
3. Test across browsers and devices
4. Respect user privacy
5. Provide clear privacy policy
6. Allow users to clear chat history

---

## 🔄 Future Enhancements

1. **Multi-language Support**: Detect visitor language and respond accordingly
2. **Custom Branding**: Allow logo, colors, fonts per bot
3. **Rich Media**: Support images, videos, buttons in responses
4. **Typing Indicators**: Real-time typing status
5. **File Uploads**: Allow visitors to upload documents
6. **Conversation Handoff**: Transfer to human agent
7. **Analytics Dashboard**: Detailed widget performance metrics
8. **A/B Testing**: Test different bot configurations
9. **Webhooks**: Notify on important events
10. **SDK Libraries**: Provide React, Vue, Angular components

---

## 📚 Related Documentation

- [Authentication System](auth.md)
- [RAG System Overview](RAG_SYSTEM_OVERVIEW.md)
- [Workspace Management](DOCUMENTATION_INDEX.md)
- [API Reference](README.md)

---

## 🤝 Support

For questions or issues with the widget system:
- Check error logs in `logs/widget_interactions.jsonl`
- Review widget token status via `/api/widget/tokens` endpoint
- Contact support with bot_id and approximate error time

---

**Last Updated**: October 17, 2025  
**Version**: 1.0.0  
**Status**: Implementation Ready
