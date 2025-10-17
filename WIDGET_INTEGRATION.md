# Widget System Integration Guide

## 🔌 Adding Widget Router to Your Application

This guide shows you exactly how to integrate the widget router into your existing FastAPI application.

---

## Step 1: Add Widget Router Import

Open `core/app.py` and add the widget router import with your other router imports.

**Location:** Around line 94, in the `include_routers()` function

**Add this line:**
```python
from routers.widget_router import router as widget_router
```

**Updated code should look like:**
```python
def include_routers(app: FastAPI):
    """Include all API routers."""
    from routers.auth_router import router as auth_router
    from routers.chat_router import router as chat_router
    from routers.data_router import router as data_router
    from routers.messages_router import router as messages_router
    from routers.conversations_router import router as conversations_router
    from routers.metrics_router import router as metrics_router
    from routers.clickup_router import router as clickup_router
    from routers.connections_router import router as connections_router
    from routers.user_management_router import router as user_management_router
    from routers.user_roles_router import router as user_roles_router
    from routers.workspace_router import router as workspace_router
    from routers.feedback_router import router as feedback_router
    from routers.user_router import router as user_router
    from routers.widget_router import router as widget_router  # ← ADD THIS LINE
    
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(data_router)
    app.include_router(messages_router)
    app.include_router(conversations_router)
    app.include_router(metrics_router)
    app.include_router(clickup_router)
    app.include_router(connections_router)
    app.include_router(user_management_router)
    app.include_router(user_roles_router)
    app.include_router(workspace_router)
    app.include_router(feedback_router)
    app.include_router(user_router)
    app.include_router(widget_router)  # ← ADD THIS LINE
    
    logger.info("All routers included")
```

---

## Step 2: Update CORS Settings (Optional but Recommended)

For widget embedding to work on external domains, you may need to update CORS settings.

**Location:** `config/settings.py`, line ~43

**Current:**
```python
cors_origins: List[str] = ["http://localhost:4200"]
```

**For Development (allow all origins):**
```python
cors_origins: List[str] = ["*"]
```

**For Production (specific domains only):**
```python
cors_origins: List[str] = [
    "http://localhost:4200",
    "https://yourdomain.com",
    "https://www.yourdomain.com"
]
```

---

## Step 3: Update Widget Base URL Setting

**Location:** `config/settings.py`

Make sure the `widget_base_url` matches your deployment:

**For Development:**
```python
widget_base_url: str = "http://localhost:8000"
```

**For Production:**
```python
widget_base_url: str = "https://api.yourdomain.com"
```

---

## Step 4: Run Database Migration

Execute the migration script to create the new tables:

```bash
python migrate_widget_system.py
```

**What this does:**
- Creates `Bot` table
- Creates `WidgetToken` table
- Creates `ChatSession` table
- Updates `Message` table with `chat_session_id` field
- Optionally creates a sample bot for testing

**Expected output:**
```
🔄 Starting Widget System migration...

📊 Creating new tables...
[SQL statements will appear here]

✅ Widget System tables created successfully!

New tables added:
  - Bot: Chatbots for embedding
  - WidgetToken: Widget authentication tokens
  - ChatSession: Visitor chat sessions
  - Message.chat_session_id: Link messages to widget sessions

❓ Create a sample bot for testing? (y/n):
```

---

## Step 5: Restart Your Application

```bash
# If using uvicorn directly
uvicorn core.app:app --reload

# Or if you have a custom startup script
python main.py
```

---

## Step 6: Verify Installation

### Check API Documentation
Navigate to: http://localhost:8000/docs

You should see new widget endpoints under the **"widget"** tag:
- `POST /widget/bots`
- `POST /widget/generate`
- `POST /widget/session/start`
- `POST /widget/chat`
- `POST /widget/refresh`
- `POST /widget/revoke`
- `GET /widget/bots`
- `GET /widget/bots/{bot_id}/sessions`
- etc.

### Test Widget.js Availability
Navigate to: http://localhost:8000/static/widget.js

You should see the JavaScript file content (not a 404).

### Test Demo Page
Navigate to: http://localhost:8000/static/widget-demo.html

You should see the beautiful demo page.

---

## Step 7: Create Your First Bot

### 7.1 Login to Get Access Token
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin"
  }'
```

**Save the `access_token` from the response.**

### 7.2 Create a Bot
```bash
curl -X POST http://localhost:8000/widget/bots \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer Support Bot",
    "description": "Helps customers with FAQs",
    "workspace_id": 1,
    "system_prompt": "You are a friendly customer support assistant. Be helpful and concise."
  }'
```

**Save the `id` from the response (this is your `bot_id`).**

### 7.3 Generate Widget Token
```bash
curl -X POST http://localhost:8000/widget/generate \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "bot_id": 1
  }'
```

**Response includes:**
```json
{
  "widget_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2025-10-24T12:00:00Z",
  "embed_code": "<script src=\"http://localhost:8000/static/widget.js\" data-bot-id=\"1\" data-token=\"eyJhbGc...\"></script>",
  "bot_id": 1,
  "bot_name": "Customer Support Bot"
}
```

---

## Step 8: Test the Widget

### Create a Test HTML File

Create `test-widget.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Widget Test</title>
</head>
<body>
    <h1>Testing Chat Widget</h1>
    <p>The widget should appear in the bottom-right corner.</p>
    
    <!-- PASTE YOUR EMBED CODE HERE -->
    <script src="http://localhost:8000/static/widget.js" 
            data-bot-id="1" 
            data-token="YOUR_WIDGET_TOKEN_HERE"
            data-api-base="http://localhost:8000/widget">
    </script>
</body>
</html>
```

### Open the Test File

```bash
# Option 1: Direct file open
# Just double-click the file or use:
open test-widget.html  # macOS
start test-widget.html  # Windows
xdg-open test-widget.html  # Linux

# Option 2: Serve via HTTP (recommended)
python -m http.server 8080
# Then navigate to: http://localhost:8080/test-widget.html
```

### Expected Behavior

1. You should see a chat bubble in the bottom-right corner
2. Click the bubble to open the chat window
3. Type a message and send it
4. The bot should respond with an intelligent answer based on your workspace content

---

## ✅ Verification Checklist

- [ ] Widget router imported in `core/app.py`
- [ ] Widget router included in `include_routers()`
- [ ] CORS configured to allow widget domains
- [ ] Database migration completed successfully
- [ ] Application restarted
- [ ] API docs show widget endpoints
- [ ] `widget.js` accessible at `/static/widget.js`
- [ ] Bot created successfully
- [ ] Widget token generated
- [ ] Widget appears on test page
- [ ] Can send and receive messages

---

## 🔧 Troubleshooting

### Issue: Widget Router Not Found

**Error:** `ModuleNotFoundError: No module named 'routers.widget_router'`

**Solution:** Make sure you created the file `routers/widget_router.py` and it's in the correct location.

### Issue: Import Errors in widget_router.py

**Error:** `ImportError: cannot import name 'Bot' from 'models'`

**Solution:** Make sure you've updated `models.py` with the new Bot, WidgetToken, and ChatSession models.

### Issue: CORS Errors in Browser Console

**Error:** `Access to fetch at 'http://localhost:8000/widget/session/start' from origin 'http://localhost:8080' has been blocked by CORS policy`

**Solution:** Update CORS origins in `config/settings.py` to include the origin where your HTML file is hosted.

### Issue: Widget Token Invalid

**Error:** `401 Unauthorized - Invalid or expired widget token`

**Solutions:**
1. Check that the token hasn't expired (7 days)
2. Verify the token is correctly copied (no spaces/line breaks)
3. Ensure the bot is still active
4. Try generating a new token

### Issue: Database Tables Not Created

**Error:** `sqlalchemy.exc.OperationalError: no such table: bot`

**Solution:** Run the migration script: `python migrate_widget_system.py`

### Issue: Widget Not Appearing

**Checklist:**
1. Check browser console for JavaScript errors
2. Verify `widget.js` is accessible
3. Confirm `data-bot-id` and `data-token` are correct
4. Check that the script tag is before `</body>`
5. Verify CORS settings

---

## 🚀 Production Deployment Checklist

Before deploying to production:

- [ ] Update `widget_base_url` to production URL
- [ ] Configure specific CORS origins (not `*`)
- [ ] Set up HTTPS for widget.js serving
- [ ] Implement rate limiting on widget endpoints
- [ ] Set up monitoring and logging
- [ ] Test token refresh mechanism
- [ ] Verify token expiration and cleanup
- [ ] Test on multiple browsers
- [ ] Test on mobile devices
- [ ] Set up analytics tracking
- [ ] Document embed code for customers
- [ ] Create customer-facing documentation

---

## 📞 Need Help?

- **Documentation:** Read `WIDGET_SYSTEM.md` for full technical details
- **Quick Start:** See `WIDGET_QUICK_START.md` for step-by-step guide
- **Demo:** Open `static/widget-demo.html` for a working example
- **API Docs:** Visit `/docs` for interactive API documentation

---

## 🎉 You're Done!

If you've completed all steps and the verification checklist, your widget system is now fully integrated and ready to use!

**Next Steps:**
1. Create production bots for your use cases
2. Customize widget appearance for your brand
3. Embed widgets on your websites
4. Monitor usage and analytics
5. Iterate based on user feedback

Happy building! 🚀
