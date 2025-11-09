# Telco Product Recommender API Documentation

## Overview

The Telco Product Recommender API is a production-ready hybrid ML-powered recommendation system for telecommunications products. It provides personalized product recommendations using collaborative filtering, content-based ranking, user segmentation, and diversity optimization.

**Version**: 1.0.0
**Base URL**: `https://api.telco-recommender.com/api/v1`
**Authentication**: JWT Bearer Token

---

## Table of Contents

1. [Authentication](#authentication)
2. [Rate Limiting](#rate-limiting)
3. [Error Handling](#error-handling)
4. [Endpoints](#endpoints)
   - [Health & Status](#health--status)
   - [Recommendations](#recommendations)
   - [Events](#events)
   - [Webhooks](#webhooks)
5. [Data Models](#data-models)
6. [Security](#security)

---

## Authentication

The API uses JWT (JSON Web Token) for authentication. Include the token in the `Authorization` header:

```http
Authorization: Bearer <your_jwt_token>
```

### Obtaining a Token

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "your_password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Token Refresh

```http
POST /api/v1/auth/refresh
Authorization: Bearer <your_current_token>
```

---

## Rate Limiting

Rate limits apply to all endpoints to ensure service stability:

- **Default**: 100 requests per minute per user/IP
- **Recommendation endpoints**: 50 requests per minute
- **Event tracking**: 200 requests per minute

Rate limit headers are included in all responses:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640000000
```

When rate limit is exceeded, the API returns:

```json
{
  "error": {
    "code": 429,
    "message": "Rate limit exceeded",
    "request_id": "req-1234567890",
    "type": "rate_limit_error"
  }
}
```

---

## Error Handling

All errors follow a consistent format:

```json
{
  "error": {
    "code": 400,
    "message": "Detailed error message",
    "request_id": "req-1234567890",
    "type": "validation_error",
    "details": [
      {
        "field": "user_id",
        "message": "Field required"
      }
    ]
  }
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 422 | Validation Error |
| 429 | Rate Limit Exceeded |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

---

## Endpoints

### Health & Status

#### GET /health

Basic health check endpoint (no authentication required).

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "production"
}
```

#### GET /health/ready

Readiness check with dependency status (no authentication required).

**Response:**
```json
{
  "status": "ready",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "mlflow": "healthy"
  }
}
```

#### GET /health/live

Liveness check (no authentication required).

**Response:**
```json
{
  "status": "alive"
}
```

---

### Recommendations

#### POST /api/v1/recommendations

Get personalized product recommendations for a user.

**Authentication**: Required
**Rate Limit**: 50 requests/minute

**Request:**
```json
{
  "user_id": "user123",
  "n_recommendations": 5,
  "context": {
    "device": "mobile",
    "location": "Jakarta",
    "time_of_day": "evening"
  },
  "filters": {
    "product_type": ["data_plan", "voice_plan"],
    "price_range": {
      "min": 50000,
      "max": 200000
    }
  }
}
```

**Response:**
```json
{
  "user_id": "user123",
  "recommendations": [
    {
      "product_id": "prod456",
      "product_name": "Data Plan 10GB",
      "score": 0.95,
      "reason": "Based on your usage patterns",
      "price": 150000,
      "features": ["10GB data", "Unlimited calls"],
      "metadata": {
        "category": "data_plan",
        "segment": "high_usage"
      }
    }
  ],
  "metadata": {
    "model_version": "v1.2.0",
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "req-1234567890",
    "strategy": "hybrid"
  }
}
```

#### GET /api/v1/recommendations/{user_id}

Get cached recommendations for a user.

**Authentication**: Required
**Rate Limit**: 100 requests/minute

**Query Parameters:**
- `n` (optional, default=5): Number of recommendations
- `refresh` (optional, default=false): Force refresh cache

**Response:** Same as POST /api/v1/recommendations

---

### Events

#### POST /api/v1/events

Track user events for model training and personalization.

**Authentication**: Required
**Rate Limit**: 200 requests/minute

**Request:**
```json
{
  "user_id": "user123",
  "event_type": "view",
  "product_id": "prod456",
  "timestamp": "2024-01-15T10:30:00Z",
  "context": {
    "device": "mobile",
    "session_id": "sess789"
  },
  "metadata": {
    "duration_seconds": 45,
    "scroll_depth": 0.8
  }
}
```

**Event Types:**
- `view`: Product viewed
- `click`: Product clicked
- `purchase`: Product purchased
- `add_to_cart`: Product added to cart
- `remove_from_cart`: Product removed from cart

**Response:**
```json
{
  "event_id": "evt-1234567890",
  "status": "recorded",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### POST /api/v1/events/batch

Track multiple events in a single request.

**Authentication**: Required
**Rate Limit**: 100 requests/minute

**Request:**
```json
{
  "events": [
    {
      "user_id": "user123",
      "event_type": "view",
      "product_id": "prod456",
      "timestamp": "2024-01-15T10:30:00Z"
    },
    {
      "user_id": "user123",
      "event_type": "click",
      "product_id": "prod789",
      "timestamp": "2024-01-15T10:31:00Z"
    }
  ]
}
```

**Response:**
```json
{
  "recorded": 2,
  "failed": 0,
  "event_ids": ["evt-123", "evt-456"]
}
```

---

### Webhooks

#### POST /api/v1/webhooks/model-update

Webhook for MLflow model updates (internal use).

**Authentication**: API Key
**Headers**: `X-API-Key: <your_api_key>`

**Request:**
```json
{
  "model_name": "lightfm_recommender",
  "version": "v1.2.0",
  "stage": "production",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## Data Models

### User

```json
{
  "user_id": "string",
  "segment": "high_value | medium_value | low_value | new_customer | churning",
  "features": {
    "total_revenue": "number",
    "tenure_days": "number",
    "avg_monthly_usage_gb": "number",
    "support_tickets": "number",
    "churn_probability": "number"
  },
  "preferences": {
    "product_types": ["string"],
    "price_sensitivity": "high | medium | low"
  }
}
```

### Product

```json
{
  "product_id": "string",
  "product_name": "string",
  "product_type": "data_plan | voice_plan | bundle | addon",
  "price": "number",
  "features": ["string"],
  "metadata": {
    "category": "string",
    "popularity_score": "number",
    "conversion_rate": "number"
  }
}
```

### Recommendation

```json
{
  "product_id": "string",
  "product_name": "string",
  "score": "number (0-1)",
  "reason": "string",
  "price": "number",
  "features": ["string"],
  "metadata": {
    "category": "string",
    "segment": "string",
    "model_confidence": "number"
  }
}
```

---

## Security

### Authentication Headers

All protected endpoints require:

```http
Authorization: Bearer <jwt_token>
X-Request-ID: <unique_request_id>
```

### Security Headers

All responses include security headers:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000
Content-Security-Policy: default-src 'self'
```

### CORS

Allowed origins are configured per environment:
- Development: `http://localhost:5173`
- Production: `https://app.telco-recommender.com`

### Rate Limiting

Rate limits are enforced per user (authenticated) or IP (unauthenticated):
- Standard: 100 requests/minute
- Recommendations: 50 requests/minute
- Events: 200 requests/minute

### Input Validation

All inputs are validated against schemas:
- Required fields must be present
- Field types must match specifications
- String lengths are limited
- Numeric ranges are enforced

---

## Examples

### Complete Recommendation Flow

```bash
# 1. Authenticate
curl -X POST https://api.telco-recommender.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user@example.com","password":"password"}'

# Response: {"access_token": "eyJ...", "token_type": "bearer"}

# 2. Get recommendations
curl -X POST https://api.telco-recommender.com/api/v1/recommendations \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "n_recommendations": 5,
    "context": {"device": "mobile"}
  }'

# 3. Track user event
curl -X POST https://api.telco-recommender.com/api/v1/events \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "event_type": "view",
    "product_id": "prod456"
  }'
```

### Error Handling Example

```python
import requests

def get_recommendations(user_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    data = {"user_id": user_id, "n_recommendations": 5}

    try:
        response = requests.post(
            "https://api.telco-recommender.com/api/v1/recommendations",
            json=data,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            # Rate limit exceeded - wait and retry
            retry_after = int(e.response.headers.get("Retry-After", 60))
            time.sleep(retry_after)
            return get_recommendations(user_id, token)
        else:
            # Handle other errors
            error = e.response.json()
            print(f"Error: {error['error']['message']}")
            raise
```

---

## Support

For API support and questions:
- **Email**: api-support@telco-recommender.com
- **Docs**: https://docs.telco-recommender.com
- **Status**: https://status.telco-recommender.com
