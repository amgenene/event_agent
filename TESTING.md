# End-to-End Testing Guide

## Quick Start

### 1. Start the API Server

```bash
# Terminal 1: Start the API
uvicorn src.api:app --reload

# You'll see:
# Uvicorn running on http://127.0.0.1:8000
# Swagger UI at http://127.0.0.1:8000/docs
```

### 2. Run End-to-End Tests

```bash
# Terminal 2: Run the test suite
python test_api_e2e.py
```

This will test all 3 endpoints with multiple scenarios.

---

## Testing Endpoints Manually

### Option A: Using Python Requests (Recommended)

```python
import httpx

client = httpx.Client()

# Health check
response = client.get("http://localhost:8000/health")
print(response.json())

# Search for events
response = client.post(
    "http://localhost:8000/search",
    json={
        "query": "Find jazz events",
        "preferences": {
            "home_city": "San Francisco",
            "favorite_genres": ["jazz"],
            "radius_miles": 10,
            "max_transit_minutes": 45
        }
    }
)
print(response.json())

# Verify an event
response = client.post(
    "http://localhost:8000/verify",
    json={
        "description": "Free jazz night. No tickets required!"
    }
)
print(response.json())
```

### Option B: Using cURL

```bash
# Health check
curl http://localhost:8000/health

# Search events
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Find music events",
    "preferences": {
      "home_city": "San Francisco",
      "favorite_genres": ["music"],
      "radius_miles": 10,
      "max_transit_minutes": 30
    }
  }'

# Verify event
curl -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Live music in the park. Free admission!"
  }'
```

### Option C: Using Swagger UI (Interactive)

1. Start the API: `uvicorn src.api:app --reload`
2. Open http://localhost:8000/docs in your browser
3. Click on each endpoint to expand it
4. Click "Try it out" to test with real requests
5. Modify JSON payloads and click "Execute"

---

## Test Scenarios

### Scenario 1: Health Check
```bash
curl http://localhost:8000/health
```
**Expected Response:**
```json
{"status": "ok"}
```

### Scenario 2: Search with Minimal Input
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Find events"}'
```

### Scenario 3: Search with Full Preferences
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Find jazz events",
    "preferences": {
      "home_city": "New York",
      "favorite_genres": ["jazz", "blues"],
      "radius_miles": 15,
      "max_transit_minutes": 60
    }
  }'
```

### Scenario 4: Verify Free Events
```bash
curl -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"description": "Free community event. No tickets required. Open to public!"}'
```

**Expected Response:**
```json
{
  "status": "FREE",
  "warnings": []
}
```

### Scenario 5: Verify Paid Events
```bash
curl -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"description": "Live band. $25 ticket required per person."}'
```

**Expected Response:**
```json
{
  "status": "PAID",
  "warnings": []
}
```

### Scenario 6: Verify Events with Warnings
```bash
curl -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"description": "Happy hour event with $5 drink minimum and suggested $10 donation."}'
```

**Expected Response:**
```json
{
  "status": "PAID",
  "warnings": [
    "Event includes suggested donation",
    "Event has drink minimum requirement"
  ]
}
```

---

## Running Unit Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src tests/

# Specific module
pytest tests/unit/test_auditor.py -v

# Integration tests only
pytest tests/integration/ -v
```

---

## Full Test Flow

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run unit tests
pytest

# 3. Start API in background
uvicorn src.api:app --reload &

# 4. Wait for API to start (2 seconds)
sleep 2

# 5. Run end-to-end tests
python test_api_e2e.py

# 6. Check Swagger docs
# Open: http://localhost:8000/docs
```

---

## Expected Behavior

### `/health` Endpoint
- **Always succeeds**
- **Purpose**: Check if API is running
- **Returns**: `{"status": "ok"}`

### `/search` Endpoint
- **Takes**: Query + optional preferences
- **Returns**: List of events (currently empty since no real APIs integrated)
- **With full integration**: Returns discovered free events

### `/verify` Endpoint
- **Takes**: Event description
- **Returns**: Status (FREE/PAID/CONDITIONAL) + warnings
- **Status**: Based on cost indicator keywords in description

---

## What's Currently Working

✅ **API Routes** - All endpoints functional  
✅ **Request Validation** - Pydantic models validate input  
✅ **Error Handling** - Proper HTTP error responses  
✅ **Unit Tests** - All components tested  
✅ **Integration** - Components work together in workflow  

## What Needs API Keys

❌ **Tavily Search** - Needs API key for real event discovery  
❌ **Nylas Calendar** - Needs API key for calendar access  
❌ **Google Maps** - Needs API key for travel time calculation  

---

## Next Steps

1. Add API keys to `.env` file
2. Integrate real API calls in each agent
3. Add mock fixtures for testing without real APIs
4. Set up Docker for local development
5. Add monitoring and logging
