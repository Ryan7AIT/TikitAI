# 🎯 Quick Frontend Code Change

## Before (Required bot_id) ❌

```javascript
// Step 1: Had to get bot_id first
const botsResponse = await fetch('/widget/bots', {
  headers: { 'Authorization': `Bearer ${accessToken}` }
});
const bots = await botsResponse.json();
const botId = bots[0]?.id;  // Get first bot

if (!botId) {
  // Had to create a bot first!
  const createBotResponse = await fetch('/widget/bots', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      name: 'My Bot',
      workspace_id: workspaceId
    })
  });
  const newBot = await createBotResponse.json();
  botId = newBot.id;
}

// Step 2: Finally generate widget
const response = await fetch('/widget/generate', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ bot_id: botId })  // Required!
});
```

---

## After (Auto-Create Bot) ✅

```javascript
// Just one call - that's it!
const response = await fetch('/widget/generate', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({})  // Empty! Bot auto-created
});

const data = await response.json();
// data.widget_token, data.embed_code, data.bot_id, data.bot_name
```

---

## Literally Just Change This:

### In your fetch call, change:
```javascript
body: JSON.stringify({ bot_id: someId })
```

### To:
```javascript
body: JSON.stringify({})
```

### That's it! ✨

---

## Optional: Custom Bot Name

```javascript
body: JSON.stringify({
  bot_name: "Customer Support Bot"
})
```

---

## Optional: Specific Bot

```javascript
body: JSON.stringify({
  bot_id: 123  // Still works if you want to specify
})
```

---

## Response (Same as Before)

```javascript
{
  widget_token: "eyJhbGc...",
  expires_at: "2025-10-24T12:00:00Z",
  embed_code: "<script src=\"...\">",
  bot_id: 1,
  bot_name: "john's Chatbot"
}
```

---

## Copy-Paste Ready Function

```javascript
async function generateWidget(accessToken, botName = null) {
  const body = botName ? { bot_name: botName } : {};
  
  const response = await fetch('/widget/generate', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  });

  if (!response.ok) {
    throw new Error('Failed to generate widget');
  }

  return await response.json();
}

// Usage:
const widget = await generateWidget(myAccessToken);
console.log(widget.embed_code);
```

Done! 🎉
