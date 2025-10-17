# Frontend Integration Guide for Widget System

## 🎯 Overview

This guide shows you **exactly what to change** in your frontend to work with the updated Widget API that now **auto-creates bots** if needed.

---

## ✅ What Changed in the Backend

The `/widget/generate` endpoint now:
- ✅ **No longer requires `bot_id` in request body**
- ✅ **Auto-creates a bot** if user doesn't have one
- ✅ **Still accepts `bot_id`** if you want to specify a particular bot
- ✅ **Accepts optional `bot_name`** for custom bot names
- ✅ **Accepts optional `workspace_id`** to specify workspace

---

## 📝 Frontend Changes Required

### **Option 1: Simplest Approach (Recommended for MVP)**

**Before:**
```javascript
// ❌ OLD CODE - Required bot_id
const response = await fetch('/widget/generate', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    bot_id: 123  // Required - had to get this somehow
  })
});
```

**After:**
```javascript
// ✅ NEW CODE - Just send empty body or no bot_id
const response = await fetch('/widget/generate', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({})  // Empty body - bot auto-created!
});

if (response.ok) {
  const data = await response.json();
  console.log('Widget Token:', data.widget_token);
  console.log('Embed Code:', data.embed_code);
  console.log('Bot ID:', data.bot_id);
  console.log('Bot Name:', data.bot_name);
}
```

---

### **Option 2: With Custom Bot Name**

```javascript
// ✅ Auto-create bot with custom name
const response = await fetch('/widget/generate', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    bot_name: "Customer Support Bot"  // Optional custom name
  })
});
```

---

### **Option 3: Advanced - Select from Existing Bots**

For a more advanced UI where users can manage multiple bots:

```javascript
// Step 1: List user's bots
async function getUserBots(accessToken) {
  const response = await fetch('/widget/bots', {
    headers: {
      'Authorization': `Bearer ${accessToken}`
    }
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch bots');
  }
  
  return await response.json();
}

// Step 2: Generate widget for specific bot OR auto-create
async function generateWidget(accessToken, botId = null) {
  const body = botId ? { bot_id: botId } : {};
  
  const response = await fetch('/widget/generate', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }
  
  return await response.json();
}

// Usage:
// Auto-create or use default bot
const widget1 = await generateWidget(accessToken);

// Use specific bot
const widget2 = await generateWidget(accessToken, 123);
```

---

## 🎨 Complete Frontend Examples

### **React Example**

```tsx
import { useState, useEffect } from 'react';

function WidgetGenerator() {
  const [accessToken, setAccessToken] = useState('');
  const [widgetData, setWidgetData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const generateWidget = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/widget/generate', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({})  // Empty - auto-creates bot
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail);
      }

      const data = await response.json();
      setWidgetData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Generate Widget</h2>
      
      <button 
        onClick={generateWidget} 
        disabled={loading || !accessToken}
      >
        {loading ? 'Generating...' : 'Generate Widget'}
      </button>

      {error && <div className="error">{error}</div>}

      {widgetData && (
        <div className="widget-info">
          <h3>Widget Generated! 🎉</h3>
          <p><strong>Bot Name:</strong> {widgetData.bot_name}</p>
          <p><strong>Bot ID:</strong> {widgetData.bot_id}</p>
          <p><strong>Expires:</strong> {new Date(widgetData.expires_at).toLocaleString()}</p>
          
          <h4>Embed Code:</h4>
          <pre>{widgetData.embed_code}</pre>
          
          <button onClick={() => navigator.clipboard.writeText(widgetData.embed_code)}>
            Copy Embed Code
          </button>
        </div>
      )}
    </div>
  );
}

export default WidgetGenerator;
```

---

### **Vue.js Example**

```vue
<template>
  <div class="widget-generator">
    <h2>Generate Widget</h2>
    
    <button 
      @click="generateWidget" 
      :disabled="loading || !accessToken"
    >
      {{ loading ? 'Generating...' : 'Generate Widget' }}
    </button>

    <div v-if="error" class="error">{{ error }}</div>

    <div v-if="widgetData" class="widget-info">
      <h3>Widget Generated! 🎉</h3>
      <p><strong>Bot Name:</strong> {{ widgetData.bot_name }}</p>
      <p><strong>Bot ID:</strong> {{ widgetData.bot_id }}</p>
      <p><strong>Expires:</strong> {{ formatDate(widgetData.expires_at) }}</p>
      
      <h4>Embed Code:</h4>
      <pre>{{ widgetData.embed_code }}</pre>
      
      <button @click="copyEmbedCode">Copy Embed Code</button>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      accessToken: '',
      widgetData: null,
      loading: false,
      error: null
    };
  },
  methods: {
    async generateWidget() {
      this.loading = true;
      this.error = null;
      
      try {
        const response = await fetch('/widget/generate', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${this.accessToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({})  // Empty - auto-creates bot
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail);
        }

        this.widgetData = await response.json();
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },
    copyEmbedCode() {
      navigator.clipboard.writeText(this.widgetData.embed_code);
      alert('Embed code copied!');
    },
    formatDate(date) {
      return new Date(date).toLocaleString();
    }
  }
};
</script>
```

---

### **Vanilla JavaScript Example**

```javascript
// Simple function you can call from anywhere
async function generateChatWidget(accessToken, customBotName = null) {
  const requestBody = customBotName 
    ? { bot_name: customBotName }
    : {};

  try {
    const response = await fetch('/widget/generate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestBody)
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to generate widget');
    }

    const data = await response.json();
    
    return {
      success: true,
      widgetToken: data.widget_token,
      embedCode: data.embed_code,
      botId: data.bot_id,
      botName: data.bot_name,
      expiresAt: data.expires_at
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
}

// Usage:
const result = await generateChatWidget(myAccessToken);

if (result.success) {
  console.log('Widget generated:', result);
  document.getElementById('embed-code').textContent = result.embedCode;
} else {
  console.error('Error:', result.error);
}
```

---

## 🎯 Complete User Flow

### **Simple Flow (No Bot Management UI)**

```javascript
// 1. User logs in and gets access token
const loginResponse = await fetch('/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username, password })
});
const { access_token } = await loginResponse.json();

// 2. User clicks "Generate Widget" button
// Bot is auto-created behind the scenes
const widgetResponse = await fetch('/widget/generate', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${access_token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({})
});
const widgetData = await widgetResponse.json();

// 3. Display embed code to user
displayEmbedCode(widgetData.embed_code);
```

---

### **Advanced Flow (With Bot Management)**

```javascript
// 1. User logs in
const { access_token } = await login(username, password);

// 2. Show bot management UI
const bots = await fetch('/widget/bots', {
  headers: { 'Authorization': `Bearer ${access_token}` }
}).then(r => r.json());

// Display bots in dropdown/list
displayBots(bots);

// 3a. User selects existing bot
const selectedBotId = getUserSelectedBotId();
const widget = await generateWidget(access_token, selectedBotId);

// OR

// 3b. User creates new bot
const newBot = await fetch('/widget/bots', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${access_token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'My New Bot',
    workspace_id: currentWorkspaceId,
    system_prompt: 'You are a helpful assistant...'
  })
}).then(r => r.json());

const widget = await generateWidget(access_token, newBot.id);

// 4. Display embed code
displayEmbedCode(widget.embed_code);
```

---

## 📦 Request/Response Examples

### **Request with Empty Body (Auto-Create)**
```http
POST /widget/generate HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{}
```

### **Request with Custom Bot Name**
```http
POST /widget/generate HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "bot_name": "Support Bot for Acme Corp"
}
```

### **Request with Specific Bot**
```http
POST /widget/generate HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "bot_id": 123
}
```

### **Success Response**
```json
{
  "widget_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiYm90X2lkIjoxLCJ0eXBlIjoid2lkZ2V0IiwiZXhwIjoxNzI5NzczNjAwLCJpYXQiOjE3MjkxNjg4MDB9.abc123...",
  "expires_at": "2025-10-24T12:00:00Z",
  "embed_code": "<script src=\"http://localhost:8000/static/widget.js\" \n        data-bot-id=\"1\" \n        data-token=\"eyJhbGc...\"\n        data-api-base=\"http://localhost:8000/widget\">\n</script>",
  "bot_id": 1,
  "bot_name": "john's Chatbot"
}
```

---

## 🛠️ Error Handling

```javascript
async function generateWidgetWithErrorHandling(accessToken) {
  try {
    const response = await fetch('/widget/generate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({})
    });

    if (!response.ok) {
      const error = await response.json();
      
      switch (response.status) {
        case 401:
          throw new Error('Authentication failed. Please login again.');
        case 400:
          throw new Error(error.detail || 'Invalid request');
        case 403:
          throw new Error('You don\'t have permission to perform this action.');
        default:
          throw new Error('An unexpected error occurred');
      }
    }

    return await response.json();
  } catch (error) {
    console.error('Widget generation failed:', error);
    throw error;
  }
}
```

---

## 📋 Summary of Changes

### **What You Need to Change:**

1. ✅ **Remove `bot_id` requirement** from your frontend code
2. ✅ **Send empty object `{}`** in request body
3. ✅ **Optionally add custom bot name** with `{ bot_name: "..." }`
4. ✅ **Handle the response** which includes bot_id and bot_name

### **What Stays the Same:**

- ✅ Still use `Authorization: Bearer <token>` header
- ✅ Still POST to `/widget/generate`
- ✅ Still receive same response structure
- ✅ Can still specify `bot_id` if you want to use specific bot

---

## 🎉 Benefits of This Update

1. **Simpler UX** - Users don't need to create bots first
2. **Fewer API Calls** - No need to call `/widget/bots` first
3. **Backward Compatible** - Still supports specifying `bot_id`
4. **Flexible** - Auto-creates workspace if needed
5. **Better DX** - Less code in your frontend

---

## 📞 Need Help?

If you encounter any issues:
1. Check the access token is valid
2. Verify user has a workspace (or let the API create one)
3. Check browser console for errors
4. Review API response for error details

---

**That's it! Your frontend should now work with just an empty request body.** 🚀
