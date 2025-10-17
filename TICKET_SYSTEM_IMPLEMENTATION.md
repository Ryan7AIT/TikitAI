# Support Ticket System Implementation

## Overview
This document describes the implementation of the support ticket generation and submission system integrated into the RAG chat application.

## Database Schema

### Ticket Table
A new `Ticket` table has been added to `models.py`:

```python
class Ticket(SQLModel, table=True):
    """Support tickets created from user conversations or manually"""
    id: Optional[int] - Primary key
    conversation_id: Optional[int] - FK to conversation (nullable)
    user_id: int - FK to user
    title: str - Ticket title (max 200 chars)
    description: str - Detailed description (TEXT)
    priority: str - "low", "medium", or "high"
    category: str - "bug", "feature", "question", or "other"
    status: str - "open", "in_progress", "resolved", or "closed"
    created_at: datetime - Creation timestamp
    updated_at: datetime - Last update timestamp
    resolved_at: Optional[datetime] - Resolution timestamp
```

## API Endpoints

### 1. Generate Ticket Endpoint

**Endpoint:** `POST /chat/generate-ticket`

**Purpose:** Analyzes a conversation and generates a support ticket structure

**Request:**
```json
{
  "conversation_id": 123  // or null
}
```

**Response:**
```json
{
  "ticket": {
    "title": "Support Request: How to export data?",
    "description": "User initiated a conversation with the following question:\n\nHow do I export data to CSV?\n\nConversation contains 5 message(s)...",
    "priority": "medium",
    "category": "question"
  }
}
```

**Features:**
- If `conversation_id` is null, returns a template ticket
- Validates that conversation exists and belongs to the requesting user
- Retrieves all messages from the conversation
- Currently generates a dummy ticket based on conversation content
- **TODO:** Replace dummy implementation with LLM-based analysis for:
  - Smart title generation
  - Comprehensive description creation
  - Automatic priority detection (based on urgency indicators)
  - Intelligent categorization (bug/feature/question/other)

**Error Handling:**
- 404: Conversation not found
- 403: User doesn't have access to the conversation
- 400: Conversation has no messages

---

### 2. Submit Ticket Endpoint

**Endpoint:** `POST /chat/submit-ticket`

**Purpose:** Creates and saves a support ticket to the database

**Request:**
```json
{
  "conversation_id": 123,  // optional
  "ticket": {
    "title": "Export feature timeout issue",
    "description": "User experiences timeout when exporting >10,000 rows to CSV...",
    "priority": "high",
    "category": "bug"
  }
}
```

**Response (Success):**
```json
{
  "success": true,
  "ticket_id": 456,
  "ticket_url": "https://support.yourapp.com/tickets/456",
  "message": "✅ Your support ticket has been successfully created! You can follow its status at: https://support.yourapp.com/tickets/456"
}
```

**Response (Error):**
```json
{
  "success": false,
  "message": "We encountered an error while creating your ticket. Please try again or contact support@yourapp.com"
}
```

**Features:**
- Validates conversation ownership if conversation_id is provided
- Validates priority (low/medium/high) and category (bug/feature/question/other)
- Creates ticket with status "open"
- Associates ticket with user and optionally with a conversation
- Returns ticket_id and URL for tracking
- Comprehensive error handling

**Error Handling:**
- 404: Conversation not found
- 403: User doesn't have access to the conversation
- 400: Invalid priority or category
- Generic errors return success=false with user-friendly message

---

## Request/Response Models

### TicketData
```python
class TicketData(BaseModel):
    title: str          # 1-200 characters
    description: str    # min 1 character
    priority: str       # "low" | "medium" | "high"
    category: str       # "bug" | "feature" | "question" | "other"
```

### GenerateTicketRequest
```python
class GenerateTicketRequest(BaseModel):
    conversation_id: int | None = None
```

### GenerateTicketResponse
```python
class GenerateTicketResponse(BaseModel):
    ticket: TicketData
```

### SubmitTicketRequest
```python
class SubmitTicketRequest(BaseModel):
    conversation_id: int | None = None
    ticket: TicketData
```

### SubmitTicketResponse
```python
class SubmitTicketResponse(BaseModel):
    success: bool
    ticket_id: int | None = None
    ticket_url: str | None = None
    message: str
```

---

## Security Features

1. **Authentication Required:** Both endpoints require valid JWT authentication via `get_current_user` dependency
2. **Conversation Ownership Validation:** Users can only access their own conversations
3. **Input Validation:** Pydantic models enforce data validation with regex patterns for priority/category
4. **SQL Injection Protection:** SQLModel/SQLAlchemy ORM prevents SQL injection attacks

---

## Future Enhancements

### High Priority
1. **LLM Integration for Ticket Generation:**
   - Replace dummy ticket generation with LLM-based conversation analysis
   - Implement intelligent title generation
   - Create comprehensive descriptions from conversation context
   - Auto-detect priority based on keywords (urgent, critical, blocking, etc.)
   - Categorize based on content (error messages → bug, "I need" → feature, etc.)

### Medium Priority
2. **Ticket Management Endpoints:**
   - `GET /chat/tickets` - List user's tickets with filtering/pagination
   - `GET /chat/tickets/{ticket_id}` - Get ticket details
   - `PATCH /chat/tickets/{ticket_id}` - Update ticket (status, priority, etc.)
   - `DELETE /chat/tickets/{ticket_id}` - Delete/close ticket

3. **Ticket Status Workflow:**
   - Implement status transitions (open → in_progress → resolved → closed)
   - Add admin endpoints for ticket management
   - Track `resolved_at` timestamp when status changes to resolved

4. **Notifications:**
   - Email notifications when tickets are created/updated
   - In-app notifications for status changes
   - Admin notifications for new tickets

### Low Priority
5. **Ticket Analytics:**
   - Dashboard for ticket metrics (response time, resolution time, etc.)
   - Category/priority distribution analytics
   - User satisfaction tracking

6. **Integration with External Ticketing Systems:**
   - Jira integration
   - Linear integration
   - Zendesk integration
   - ClickUp tasks integration (already have ClickUp connection infrastructure)

---

## Database Migration

After implementing this feature, you'll need to run a database migration to create the `ticket` table:

```bash
# If using Alembic:
alembic revision --autogenerate -m "Add ticket table"
alembic upgrade head

# Or if using direct SQLModel table creation:
# The table will be created automatically on first run if using create_db_and_tables()
```

---

## Testing Recommendations

### Manual Testing
1. Test generate-ticket with null conversation_id (should return template)
2. Test generate-ticket with valid conversation_id
3. Test generate-ticket with non-existent conversation_id (should 404)
4. Test generate-ticket with another user's conversation (should 403)
5. Test submit-ticket with valid data
6. Test submit-ticket with invalid priority/category
7. Test submit-ticket error handling

### Integration Testing
```python
# Example test cases needed:
- test_generate_ticket_without_conversation()
- test_generate_ticket_with_conversation()
- test_generate_ticket_unauthorized_conversation()
- test_submit_ticket_success()
- test_submit_ticket_invalid_priority()
- test_submit_ticket_invalid_category()
- test_submit_ticket_with_conversation()
```

---

## Configuration

Update the ticket URL generation in `submit_ticket_endpoint`:
```python
# Line ~322 in chat_router.py
ticket_url = f"https://support.yourapp.com/tickets/{new_ticket.id}"
```

Replace `https://support.yourapp.com` with your actual support system URL or configure it in `config/settings.py`.

---

## Implementation Checklist

- [x] Create Ticket model in models.py
- [x] Create request/response Pydantic models
- [x] Implement POST /chat/generate-ticket endpoint
- [x] Implement POST /chat/submit-ticket endpoint
- [x] Add authentication and authorization
- [x] Add error handling
- [x] Add logging
- [ ] Run database migration
- [ ] Replace dummy ticket generation with LLM
- [ ] Configure ticket URL in settings
- [ ] Add unit tests
- [ ] Add integration tests
- [ ] Update API documentation

---

## Notes

- Both endpoints are now accessible at `/chat/generate-ticket` and `/chat/submit-ticket`
- The dummy ticket generation is clearly marked with TODO comments for LLM implementation
- All user inputs are validated using Pydantic models with regex patterns
- Comprehensive logging is implemented for debugging and monitoring
- Error responses follow FastAPI/HTTP standards
