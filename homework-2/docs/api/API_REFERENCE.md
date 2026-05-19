# API Reference

Complete documentation of the Ticket Support API.

---

## Base URL

```
http://localhost:3000
```

---

## Authentication

Currently no authentication required. (Production: implement API keys/JWT)

---

## Data Models

### Ticket

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "customer_id": "C-123",
  "customer_email": "user@example.com",
  "customer_name": "John Doe",
  "subject": "Cannot login",
  "description": "I cannot access my account and cannot reset my password.",
  "category": "account_access",
  "priority": "urgent",
  "status": "new",
  "created_at": "2024-05-19T10:30:00Z",
  "updated_at": "2024-05-19T10:30:00Z",
  "resolved_at": null,
  "assigned_to": "agent-1",
  "tags": ["urgent", "login"],
  "metadata": {
    "source": "web_form",
    "browser": "Chrome",
    "device_type": "desktop"
  },
  "classification": {
    "category": "account_access",
    "priority": "urgent",
    "confidence": 0.85,
    "reasoning": "Category 'account_access' chosen due to keywords [can't access, password]; priority 'urgent' due to [can't access].",
    "keywords_found": ["can't access", "password"]
  }
}
```

### Enums

**Category**
- `account_access` — Login, password, 2FA issues
- `technical_issue` — Bugs, errors, crashes
- `billing_question` — Payments, invoices, refunds
- `feature_request` — Enhancements, suggestions
- `bug_report` — Defects with steps to reproduce
- `other` — Uncategorizable (default)

**Priority**
- `urgent` — Critical, production down
- `high` — Important, blocking
- `medium` — Normal (default)
- `low` — Minor, cosmetic

**Status**
- `new` — Just created (default)
- `in_progress` — Being worked on
- `waiting_customer` — Awaiting customer response
- `resolved` — Fixed or answered
- `closed` — Finalized

**Source**
- `web_form` — Via web form
- `email` — Via email
- `api` — Via API
- `chat` — Via live chat
- `phone` — Via phone call

**Device**
- `desktop`
- `mobile`
- `tablet`

---

## Endpoints

### 1. Create Ticket

**Request**

```
POST /tickets
Content-Type: application/json
```

**Body** (required fields: customer_id, customer_email, customer_name, subject, description, metadata.source)

```json
{
  "customer_id": "C-123",
  "customer_email": "user@example.com",
  "customer_name": "John",
  "subject": "Cannot login",
  "description": "I cannot access my account. Please help me reset the password.",
  "category": "account_access",
  "priority": "high",
  "status": "new",
  "assigned_to": "agent-1",
  "tags": ["urgent", "account"],
  "metadata": {
    "source": "web_form",
    "browser": "Chrome",
    "device_type": "desktop"
  }
}
```

**Query Parameters**

- `autoClassify=true` (optional) — Auto-classify the ticket using keywords

**Response**

```
201 Created
```

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "customer_id": "C-123",
  "customer_email": "user@example.com",
  "customer_name": "John",
  "subject": "Cannot login",
  "description": "I cannot access my account. Please help me reset the password.",
  "category": "account_access",
  "priority": "high",
  "status": "new",
  "created_at": "2024-05-19T10:30:00Z",
  "updated_at": "2024-05-19T10:30:00Z",
  "resolved_at": null,
  "assigned_to": "agent-1",
  "tags": ["urgent", "account"],
  "metadata": {
    "source": "web_form",
    "browser": "Chrome",
    "device_type": "desktop"
  }
}
```

**Errors**

```
400 Bad Request
{
  "error": "validation_error",
  "details": [
    {
      "path": "customer_email",
      "message": "Invalid email"
    }
  ]
}
```

**cURL**

```bash
curl -X POST http://localhost:3000/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "C-1",
    "customer_email": "user@example.com",
    "customer_name": "John",
    "subject": "Cannot login",
    "description": "I cannot access my account password reset.",
    "metadata": { "source": "web_form" }
  }'
```

---

### 2. Bulk Import Tickets

**Request**

```
POST /tickets/import
Content-Type: multipart/form-data
```

**Form Data**

- `file` (required) — CSV, JSON, or XML file (max 5MB)

**Query Parameters**

- `autoClassify=true` (optional) — Auto-classify imported tickets

**Response**

```
200 OK
```

```json
{
  "total": 50,
  "successful": 48,
  "failed": [
    {
      "row": 15,
      "errors": ["customer_email: Invalid email"]
    },
    {
      "row": 32,
      "errors": ["subject: String must contain at least 1 character"]
    }
  ],
  "tickets": [
    { "id": "...", "customer_id": "C-100" },
    { "id": "...", "customer_id": "C-101" }
  ]
}
```

**File Formats**

**CSV**

```csv
customer_id,customer_email,customer_name,subject,description,category,priority,status,tags,metadata.source,metadata.browser,metadata.device_type
C-100,bob@example.com,Bob,Cannot login,I cannot access my account,account_access,urgent,new,"login,urgent",web_form,Chrome,desktop
C-101,carol@example.com,Carol,Refund needed,I would like a refund,billing_question,medium,new,"refund,billing",email,Firefox,mobile
```

**JSON** (top-level array or wrapped)

```json
[
  {
    "customer_id": "C-200",
    "customer_email": "dave@example.com",
    "customer_name": "Dave",
    "subject": "App crashes",
    "description": "Application crashes on startup.",
    "metadata": { "source": "api" }
  }
]
```

or

```json
{
  "tickets": [
    { "customer_id": "C-300" }
  ]
}
```

**XML**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<tickets>
  <ticket>
    <customer_id>C-400</customer_id>
    <customer_email>erin@example.com</customer_email>
    <customer_name>Erin</customer_name>
    <subject>Security incident</subject>
    <description>Possible security issue detected.</description>
    <tags>
      <tag>security</tag>
      <tag>urgent</tag>
    </tags>
    <metadata>
      <source>email</source>
      <browser>Safari</browser>
      <device_type>desktop</device_type>
    </metadata>
  </ticket>
</tickets>
```

**cURL**

```bash
curl -X POST http://localhost:3000/tickets/import \
  -F "file=@tickets.csv"

curl -X POST "http://localhost:3000/tickets/import?autoClassify=true" \
  -F "file=@tickets.json"
```

---

### 3. List Tickets

**Request**

```
GET /tickets
```

**Query Parameters**

- `category` (optional) — Filter by category (e.g., `account_access`)
- `priority` (optional) — Filter by priority (e.g., `urgent`)
- `status` (optional) — Filter by status (e.g., `new`)
- `assigned_to` (optional) — Filter by assigned agent
- `customer_id` (optional) — Filter by customer ID

**Response**

```
200 OK
```

```json
{
  "count": 15,
  "tickets": [
    { "id": "550e8400-...", "customer_id": "C-1" },
    { "id": "550e8401-...", "customer_id": "C-2" }
  ]
}
```

**cURL**

```bash
curl "http://localhost:3000/tickets"

curl "http://localhost:3000/tickets?category=account_access&priority=urgent"

curl "http://localhost:3000/tickets?status=in_progress&assigned_to=agent-1"
```

---

### 4. Get Single Ticket

**Request**

```
GET /tickets/:id
```

**Response**

```
200 OK
```

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "customer_id": "C-1"
}
```

**Error**

```
404 Not Found
{
  "error": "ticket not found"
}
```

**cURL**

```bash
curl "http://localhost:3000/tickets/550e8400-e29b-41d4-a716-446655440000"
```

---

### 5. Update Ticket

**Request**

```
PUT /tickets/:id
Content-Type: application/json
```

**Body** (all fields optional)

```json
{
  "status": "resolved",
  "assigned_to": "agent-2",
  "priority": "high",
  "tags": ["resolved", "escalated"]
}
```

**Response**

```
200 OK
```

```json
{
  "id": "550e8400-...",
  "status": "resolved",
  "resolved_at": "2024-05-19T11:00:00Z",
  "updated_at": "2024-05-19T11:00:00Z"
}
```

**cURL**

```bash
curl -X PUT http://localhost:3000/tickets/550e8400-e29b-41d4-a716-446655440000 \
  -H "Content-Type: application/json" \
  -d '{ "status": "resolved" }'
```

---

### 6. Delete Ticket

**Request**

```
DELETE /tickets/:id
```

**Response**

```
204 No Content
```

**cURL**

```bash
curl -X DELETE http://localhost:3000/tickets/550e8400-e29b-41d4-a716-446655440000
```

---

### 7. Auto-Classify Ticket

**Request**

```
POST /tickets/:id/auto-classify
```

**Response**

```
200 OK
```

```json
{
  "ticket": {
    "id": "550e8400-...",
    "category": "account_access",
    "priority": "urgent",
    "classification": {}
  },
  "classification": {
    "category": "account_access",
    "priority": "urgent",
    "confidence": 0.85,
    "reasoning": "Category 'account_access' chosen due to keywords [can't access]; priority 'urgent' due to [can't access].",
    "keywords_found": ["can't access"]
  }
}
```

**cURL**

```bash
curl -X POST http://localhost:3000/tickets/550e8400-e29b-41d4-a716-446655440000/auto-classify
```

---

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK |
| 201 | Created |
| 204 | No Content |
| 400 | Bad Request (validation error) |
| 404 | Not Found |
| 500 | Internal Server Error |

---

## Error Response Format

```json
{
  "error": "error_code",
  "details": "Human-readable message or array of validation errors"
}
```

**Validation Error Example**

```json
{
  "error": "validation_error",
  "details": [
    {
      "path": "customer_email",
      "message": "Invalid email"
    },
    {
      "path": "description",
      "message": "String must contain at least 10 characters"
    }
  ]
}
```

---

## Rate Limiting

Currently not implemented. (Production: add rate limiting middleware)

---

## Pagination

Currently not implemented. Use filtering (`?status=new&priority=urgent`) instead.

---

## Best Practices

1. **Always validate** input data client-side before sending
2. **Use appropriate filters** to reduce response size
3. **Check error responses** for validation details
4. **Handle 404** gracefully — ticket may have been deleted
5. **Retry on 500** with exponential backoff
6. **Cache GET** responses when appropriate

---

## Examples

### Complete Workflow

```bash
# 1. Create a ticket
TICKET=$(curl -X POST http://localhost:3000/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "C-1",
    "customer_email": "user@example.com",
    "customer_name": "John",
    "subject": "Cannot login",
    "description": "I cannot access my account.",
    "metadata": { "source": "web_form" }
  }')

ID=$(echo $TICKET | jq -r '.id')

# 2. Auto-classify it
curl -X POST "http://localhost:3000/tickets/$ID/auto-classify"

# 3. Update status
curl -X PUT "http://localhost:3000/tickets/$ID" \
  -H "Content-Type: application/json" \
  -d '{ "status": "in_progress", "assigned_to": "agent-1" }'

# 4. List all urgent tickets
curl "http://localhost:3000/tickets?priority=urgent"

# 5. Resolve and delete
curl -X PUT "http://localhost:3000/tickets/$ID" \
  -H "Content-Type: application/json" \
  -d '{ "status": "resolved" }'

curl -X DELETE "http://localhost:3000/tickets/$ID"
```

---

For implementation details, see [ARCHITECTURE.md](../architecture/ARCHITECTURE.md).
For project setup, see [README.md](../../README.md).
