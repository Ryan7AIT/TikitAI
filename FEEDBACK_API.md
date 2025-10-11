# Feedback System API Documentation

## Overview
The Feedback System allows users to submit feature requests and bug reports, vote on them, and track their status.

## Models Added to `models.py`

### 1. **Feedback**
Main table for storing feedback items (features and bugs).

**Fields:**
- `id`: Primary key
- `type`: "feature" or "bug"
- `title`: Title of the feedback (max 255 chars)
- `description`: Detailed description
- `category`: Optional category classification
- `priority`: "low", "medium", or "high"
- `status`: "pending", "in-progress", "completed", or "rejected"
- `votes`: Number of upvotes
- `author_id`: Foreign key to User
- `workspace_id`: Foreign key to Workspace (optional)
- `created_at`: Timestamp
- `updated_at`: Timestamp
- `deleted_at`: Soft delete timestamp

### 2. **FeedbackVote**
Tracks user votes on feedback items (prevents duplicate voting).

**Fields:**
- `id`: Primary key
- `feedback_id`: Foreign key to Feedback
- `user_id`: Foreign key to User
- `created_at`: Timestamp

### 3. **FeedbackComment**
Comments on feedback items (for future enhancement).

**Fields:**
- `id`: Primary key
- `feedback_id`: Foreign key to Feedback
- `author_id`: Foreign key to User
- `content`: Comment text
- `votes`: Number of upvotes on the comment
- `created_at`: Timestamp
- `updated_at`: Timestamp
- `deleted_at`: Soft delete timestamp

---

## API Endpoints

### Base URL: `/api/feedback`

### 1. **GET /api/feedback/features**
Get all feature requests with filtering and pagination.

**Query Parameters:**
- `status` (optional): Filter by status - `pending`, `in-progress`, `completed`, `rejected`
- `sort` (optional): Sort order - `newest`, `oldest`, `popular`, `priority` (default: `newest`)
- `page` (optional): Page number (default: 1)
- `limit` (optional): Items per page, max 100 (default: 10)

**Example:**
```
GET /api/feedback/features?status=pending&sort=popular&page=1&limit=10
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "type": "feature",
      "title": "Dark Mode Toggle",
      "description": "Add dark mode...",
      "category": "UI/UX",
      "priority": "high",
      "status": "pending",
      "votes": 15,
      "hasVoted": false,
      "author": {
        "id": 1,
        "name": "john_doe",
        "avatar": "JD"
      },
      "createdAt": "2024-10-01T10:30:00",
      "updatedAt": "2024-10-05T14:20:00",
      "comments": 3,
      "tags": []
    }
  ],
  "pagination": {
    "currentPage": 1,
    "totalPages": 5,
    "totalItems": 47,
    "itemsPerPage": 10
  }
}
```

---

### 2. **GET /api/feedback/bugs**
Get all bug reports (same parameters and response structure as features).

**Query Parameters:** Same as `/features`

---

### 3. **POST /api/feedback**
Create a new feedback item.

**Request Body:**
```json
{
  "type": "feature",
  "title": "Export to Excel",
  "description": "Allow users to export data to Excel format",
  "priority": "medium",
  "category": "Analytics"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Feedback submitted successfully",
  "data": {
    "id": 10,
    "type": "feature",
    "title": "Export to Excel",
    "description": "Allow users to export data to Excel format",
    "category": "Analytics",
    "priority": "medium",
    "status": "pending",
    "votes": 0,
    "hasVoted": false,
    "author": {
      "id": 2,
      "name": "current_user",
      "avatar": "CU"
    },
    "createdAt": "2024-10-08T15:30:00",
    "updatedAt": "2024-10-08T15:30:00",
    "comments": 0,
    "tags": []
  }
}
```

---

### 4. **POST /api/feedback/{id}/upvote**
Add an upvote to a feedback item.

**Example:**
```
POST /api/feedback/5/upvote
```

**Response:**
```json
{
  "success": true,
  "message": "Upvote added successfully",
  "data": {
    "votes": 16,
    "hasVoted": true
  }
}
```

**Error Cases:**
- 404: Feedback not found
- 400: Already voted

---

### 5. **DELETE /api/feedback/{id}/upvote**
Remove an upvote from a feedback item.

**Example:**
```
DELETE /api/feedback/5/upvote
```

**Response:**
```json
{
  "success": true,
  "message": "Upvote removed successfully",
  "data": {
    "votes": 15,
    "hasVoted": false
  }
}
```

**Error Cases:**
- 404: Feedback not found
- 400: Not voted yet

---

### 6. **GET /api/feedback/{id}**
Get detailed information about a specific feedback item.

**Example:**
```
GET /api/feedback/5
```

**Response:**
```json
{
  "success": true,
  "message": "Feedback retrieved successfully",
  "data": {
    "id": 5,
    "type": "feature",
    "title": "Dark Mode Toggle",
    "description": "Add dark mode support...",
    "category": "UI/UX",
    "priority": "high",
    "status": "in-progress",
    "votes": 15,
    "hasVoted": true,
    "author": {
      "id": 1,
      "name": "john_doe",
      "avatar": "JD"
    },
    "createdAt": "2024-10-01T10:30:00",
    "updatedAt": "2024-10-05T14:20:00",
    "comments": 3,
    "tags": []
  }
}
```

---

### 7. **PATCH /api/feedback/{id}/status** (Admin Only)
Update the status of a feedback item.

**Request Body:**
```json
{
  "status": "in-progress",
  "adminNote": "Working on this for v2.0"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Status updated successfully",
  "data": {
    "id": 5,
    "status": "in-progress",
    "updatedAt": "2024-10-08T15:45:00"
  }
}
```

**Authentication:** Requires admin privileges (uses `require_admin` dependency)

---

## Authentication
All endpoints require authentication via JWT Bearer token in the Authorization header:
```
Authorization: Bearer <your-jwt-token>
```

---

## Features Implemented

✅ **Core Functionality:**
- Create feature requests and bug reports
- Vote/unvote on feedback items
- Filter by status and type
- Sort by newest, oldest, or popularity
- Pagination support
- Soft deletes (deleted_at field)

✅ **Security:**
- All endpoints require authentication
- Vote tracking prevents duplicate votes
- Admin-only status updates
- Workspace isolation (feedback tied to workspaces)

✅ **Data Integrity:**
- Foreign key relationships
- Unique constraints on votes (one vote per user per item)
- Proper indexing for performance

✅ **Response Structure:**
- Consistent API responses with success flags
- Pagination metadata
- User-friendly author information with initials

---

## Database Tables Created

When you start the application, the following tables will be automatically created:

1. **feedback** - Main feedback storage
2. **feedbackvote** - Vote tracking
3. **feedbackcomment** - Comments (ready for future use)

---

## Future Enhancements

The system is ready for these features:
- Comments on feedback items (model already exists)
- Tags system (can be added to Feedback model)
- Admin notes and status history
- Email notifications
- Advanced filtering by category
- Search functionality

---

## Testing the API

You can test the endpoints using:

1. **Swagger UI**: Navigate to `/docs` when your app is running
2. **Postman/Thunder Client**: Import the endpoints
3. **curl** examples:

```bash
# Get all features
curl -X GET "http://localhost:8000/api/feedback/features" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Create a feature request
curl -X POST "http://localhost:8000/api/feedback" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "feature",
    "title": "Export to PDF",
    "description": "Add PDF export functionality",
    "priority": "medium",
    "category": "Export"
  }'

# Upvote a feedback item
curl -X POST "http://localhost:8000/api/feedback/1/upvote" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Integration with Frontend

The API responses match the structure expected by your frontend developer. Key points:

- `hasVoted` field indicates if current user has voted
- Author information includes initials for avatars
- Pagination data for infinite scroll or page navigation
- All timestamps in ISO format
- Consistent error responses with proper HTTP status codes
