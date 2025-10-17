# Widget System Quick Start Guide

## 🚀 Getting Started

This guide will help you set up and use the embeddable chat widget system in 5 minutes.

## 📋 Prerequisites

- Running RAG Chat API instance
- Admin account or user account with workspace access
- Access token for API authentication

## 🔧 Installation Steps

### 1. Run Database Migration

First, update your database to include the new widget tables:

```bash
python migrate_widget_system.py
```

This will:
- Create `Bot`, `WidgetToken`, and `ChatSession` tables
- Update `Message` table to support widget sessions
- Optionally create a sample bot for testing

### 2. Update Main Application

Add the widget router to your `main.py` or `app.py`:

```python
from routers import widget_router

app.include_router(widget_router.router, prefix="/widget")
```

### 3. Configure CORS (Important!)

Update your CORS settings to allow widget requests from external domains:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 4. Restart Your Application

```bash
uvicorn main:app --reload
```

## 🤖 Creating Your First Bot

### Step 1: Authenticate

Get your access token:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin"
  }'
```

Save the `access_token` from the response.

### Step 2: Create a Bot

```bash
curl -X POST http://localhost:8000/widget/bots \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer Support Bot",
    "description": "Helps customers with common questions",
    "workspace_id": 1,
    "system_prompt": "You are a friendly customer support assistant. Be helpful and concise."
  }'
```

Save the `bot_id` from the response.

### Step 3: Generate Widget Token

```bash
curl -X POST http://localhost:8000/widget/generate \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "bot_id": 1
  }'
```

Response will include:
- `widget_token`: The JWT token for authentication
- `embed_code`: Ready-to-use HTML snippet
- `expires_at`: Token expiration date

## 🌐 Embedding the Widget

### Basic Embed

Copy the `embed_code` from the previous step and paste it into any HTML page:

```html
<!DOCTYPE html>
<html>
<head>
    <title>My Website</title>
</head>
<body>
    <h1>Welcome to My Website</h1>
    
    <!-- Chat Widget -->
    <script src="http://localhost:8000/static/widget.js" 
            data-bot-id="1" 
            data-token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            data-api-base="http://localhost:8000/widget">
    </script>
</body>
</html>
```

### Customization Options

```html
<script src="http://localhost:8000/static/widget.js" 
        data-bot-id="1" 
        data-token="YOUR_WIDGET_TOKEN"
        data-api-base="http://localhost:8000/widget"
        data-theme="light"              <!-- or "dark" -->
        data-position="bottom-right"    <!-- or bottom-left, top-right, top-left -->
        data-primary-color="#3b82f6"    <!-- Custom brand color -->
        data-bubble-icon="💬">          <!-- Custom icon or emoji -->
</script>
```

## 🎨 Customization Examples

### Dark Theme with Custom Colors

```html
<script src="http://localhost:8000/static/widget.js" 
        data-bot-id="1" 
        data-token="YOUR_TOKEN"
        data-theme="dark"
        data-primary-color="#8b5cf6"
        data-bubble-icon="🤖">
</script>
```

### Top-Left Position

```html
<script src="http://localhost:8000/static/widget.js" 
        data-bot-id="1" 
        data-token="YOUR_TOKEN"
        data-position="top-left">
</script>
```

## 📊 Managing Your Bots

### List All Your Bots

```bash
curl -X GET http://localhost:8000/widget/bots \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Update a Bot

```bash
curl -X PUT http://localhost:8000/widget/bots/1 \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Bot Name",
    "is_active": true,
    "system_prompt": "Updated system prompt"
  }'
```

### View Bot Sessions

```bash
curl -X GET http://localhost:8000/widget/bots/1/sessions \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Deactivate a Bot

```bash
curl -X PUT http://localhost:8000/widget/bots/1 \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "is_active": false
  }'
```

## 🔐 Security Best Practices

### 1. Token Rotation

Rotate widget tokens regularly (recommended: every 30 days):

```bash
# Revoke old token
curl -X POST http://localhost:8000/widget/revoke \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"bot_id": 1}'

# Generate new token
curl -X POST http://localhost:8000/widget/generate \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"bot_id": 1}'
```

### 2. CORS Configuration

In production, restrict CORS to specific domains:

```python
allow_origins=[
    "https://yourdomain.com",
    "https://www.yourdomain.com"
]
```

### 3. Rate Limiting

Implement rate limiting on widget endpoints (recommended setup):

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/chat")
@limiter.limit("30/minute")
async def send_message(...):
    ...
```

## 🧪 Testing the Widget

### 1. Create a Test HTML File

```html
<!-- test-widget.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Widget Test</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            padding: 20px;
            max-width: 800px;
            margin: 0 auto;
        }
        h1 { color: #333; }
        p { color: #666; line-height: 1.6; }
    </style>
</head>
<body>
    <h1>Chat Widget Test Page</h1>
    <p>
        This is a test page to verify the chat widget integration.
        The widget should appear in the bottom-right corner.
    </p>
    <p>
        Try clicking on the chat bubble to open the widget and send a message!
    </p>
    
    <script src="http://localhost:8000/static/widget.js" 
            data-bot-id="1" 
            data-token="YOUR_WIDGET_TOKEN"
            data-api-base="http://localhost:8000/widget">
    </script>
</body>
</html>
```

### 2. Open in Browser

```bash
# Start a simple HTTP server
python -m http.server 8080

# Open in browser
# http://localhost:8080/test-widget.html
```

## 📈 Monitoring & Analytics

### Check Bot Statistics

```bash
curl -X GET http://localhost:8000/widget/bots \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Response includes:
- `total_sessions`: Total chat sessions created
- `active_tokens`: Number of valid widget tokens
- Bot status and configuration

### View Active Sessions

```bash
curl -X GET "http://localhost:8000/widget/bots/1/sessions?active_only=true" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 🔄 Token Refresh

Widget tokens automatically refresh when they expire. The widget.js handles this transparently.

Manual refresh (if needed):

```bash
curl -X POST http://localhost:8000/widget/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "widget_token": "YOUR_EXPIRED_TOKEN"
  }'
```

## 🐛 Troubleshooting

### Widget Not Appearing

1. **Check browser console** for errors
2. **Verify CORS settings** - should allow your domain
3. **Check token validity** - tokens expire after 7 days
4. **Verify bot is active** - inactive bots won't work

### Messages Not Sending

1. **Check session status** - sessions may have expired
2. **Verify workspace has content** - bot needs data to respond
3. **Check API logs** for errors
4. **Verify network connectivity**

### Token Expired Error

```bash
# Generate a new token
curl -X POST http://localhost:8000/widget/generate \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"bot_id": 1}'

# Update the embed code with the new token
```

## 📚 API Reference

| Endpoint                     | Method | Auth         | Description           |
| ---------------------------- | ------ | ------------ | --------------------- |
| `/widget/bots`               | GET    | Access Token | List user's bots      |
| `/widget/bots`               | POST   | Access Token | Create new bot        |
| `/widget/bots/{id}`          | PUT    | Access Token | Update bot            |
| `/widget/bots/{id}`          | DELETE | Access Token | Delete bot            |
| `/widget/generate`           | POST   | Access Token | Generate widget token |
| `/widget/session/start`      | POST   | Widget Token | Start chat session    |
| `/widget/chat`               | POST   | Widget Token | Send message          |
| `/widget/refresh`            | POST   | None         | Refresh expired token |
| `/widget/revoke`             | POST   | Access Token | Revoke token(s)       |
| `/widget/bots/{id}/sessions` | GET    | Access Token | List bot sessions     |

## 🎯 Next Steps

1. **Customize the widget** appearance to match your brand
2. **Add more bots** for different use cases
3. **Monitor analytics** to improve responses
4. **Set up alerts** for high-traffic periods
5. **Implement rate limiting** for production
6. **Configure proper CORS** for security

## 💡 Pro Tips

- **Use descriptive bot names** to track them easily
- **Set clear system prompts** for better responses
- **Test thoroughly** before deploying to production
- **Monitor token usage** to detect unauthorized access
- **Keep workspace content updated** for accurate responses
- **Use different bots** for different pages/purposes

## 🆘 Support

For issues or questions:
- Check the main [WIDGET_SYSTEM.md](WIDGET_SYSTEM.md) documentation
- Review API logs in `logs/` directory
- Check database state for debugging
- Verify all environment variables are set

---

**Happy Building! 🚀**
