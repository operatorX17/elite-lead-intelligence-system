# Troubleshooting: Discover Leads Not Returning Data

## Problem
Claude 3.5 Sonnet calls the `discoverLeads` tool but doesn't show any leads. The AI says "Here are 20 SaaS leads" but no data appears.

## Root Cause
**Timeout Mismatch**: The frontend tool times out (was 2 minutes) before the backend Apify scraper finishes (can take 5 minutes).

## Solution Applied

### 1. Increased Frontend Timeout ✅
**File**: `frontend/lib/zrai/constants.ts`
```typescript
// Changed from 120000 (2 min) to 300000 (5 min)
export const LONG_OPERATION_TIMEOUT_MS = 300000;
```

### 2. Added Mock Mode for Fast Testing ✅
**Files**: 
- `src/api/server.py` - Added `mock` parameter to DiscoverRequest
- `frontend/app/(chat)/api/zrai/discover/route.ts` - Pass through mock flag
- `frontend/lib/ai/tools/zrai/discover-leads.ts` - Default to `mock=true` in development

**Usage**:
```typescript
// Fast mock data (instant response)
discoverLeads({ niche: "saas", geo: "us", limit: 20, mock: true })

// Real data from Google Maps (2-5 minutes)
discoverLeads({ niche: "saas", geo: "us", limit: 20, mock: false })
```

### 3. Added Better Logging ✅
Console logs now show:
- When discovery starts
- Response status
- Success/failure details
- Error messages

## Testing

### Quick Test (Mock Data - Instant)
```bash
# 1. Start backend
python run.py

# 2. Start frontend
cd frontend && pnpm dev

# 3. In chat, ask:
"Find me 20 SaaS leads in the US"

# Expected: Instant response with mock data
```

### Real Test (Apify - Slow but Real)
```bash
# In chat, ask:
"Find me 5 real SaaS leads in the US using Apify"

# Expected: 2-5 minute wait, then real Google Maps data
```

### Backend Direct Test
```bash
# Test mock mode
python test_backend_discover.py

# Or manually:
curl -X POST http://localhost:8000/api/v1/discover \
  -H "Content-Type: application/json" \
  -d '{"niche":"saas","geo":"us","limit":5,"mock":true}'
```

## Why It Was Failing

### Timeline of a Failed Request:
```
0:00 - User asks for leads
0:01 - Frontend calls /api/zrai/discover
0:02 - Frontend calls backend /api/v1/discover
0:03 - Backend starts Apify Google Maps scraper
...
2:00 - Frontend timeout (120s) - ABORTS REQUEST
...
5:00 - Backend finishes (300s) - but frontend already gave up
```

### Timeline Now (Mock Mode):
```
0:00 - User asks for leads
0:01 - Frontend calls /api/zrai/discover with mock=true
0:02 - Backend returns mock data instantly
0:03 - Frontend receives data
0:04 - AI displays leads in artifact
```

### Timeline Now (Real Mode):
```
0:00 - User asks for leads
0:01 - Frontend calls /api/zrai/discover with mock=false
0:02 - Backend starts Apify Google Maps scraper
...
5:00 - Backend finishes (300s)
5:01 - Frontend receives data (timeout now 300s)
5:02 - AI displays leads in artifact
```

## Common Issues

### Issue 1: Still No Leads Showing
**Check**:
1. Open browser DevTools → Console
2. Look for `[discoverLeads]` logs
3. Check if there's an error message

**Solutions**:
- If timeout: Use `mock=true`
- If 503 error: Backend not running (`python run.py`)
- If 401 error: Not logged in to frontend

### Issue 2: Mock Data Not Working
**Check**:
```bash
# Test backend directly
curl -X POST http://localhost:8000/api/v1/discover \
  -H "Content-Type: application/json" \
  -d '{"niche":"saas","geo":"us","limit":5,"mock":true}'
```

**Expected Response**:
```json
{
  "leads": [
    {
      "id": "...",
      "company_name": "SAAS Company 1",
      "domain": "company1.com",
      ...
    }
  ],
  "count": 5,
  "run_id": "..."
}
```

### Issue 3: Real Apify Data Not Working
**Check**:
1. Apify API token configured: `echo $APIFY_API_TOKEN`
2. Backend logs for errors: Check terminal running `python run.py`
3. Apify account has credits

**Solutions**:
- Verify token in `.env`: `APIFY_API_TOKEN=apify_api_...`
- Check Apify dashboard for usage/credits
- Try with smaller limit: `limit=5` instead of `limit=20`

## Environment Variables

Required in `.env`:
```bash
# For real data
APIFY_API_TOKEN=apify_api_mXCW0rv3b8c922obYDB6l6waguEei13VjwBO

# For backend connection
ZRAI_BACKEND_URL=http://localhost:8000  # In frontend/.env.local
```

## Architecture Flow

```
User Query
    ↓
Claude 3.5 Sonnet (with tools enabled)
    ↓
discoverLeads tool (frontend/lib/ai/tools/zrai/discover-leads.ts)
    ↓
POST /api/zrai/discover (frontend/app/(chat)/api/zrai/discover/route.ts)
    ↓
POST /api/v1/discover (src/api/server.py)
    ↓
    ├─ mock=true → Instant mock data
    └─ mock=false → Apify Google Maps scraper (2-5 min)
    ↓
Response with leads array
    ↓
AI displays in lead-list artifact
```

## Performance Comparison

| Mode | Speed | Data Quality | Use Case |
|------|-------|--------------|----------|
| Mock | Instant | Fake | Development, testing, demos |
| Real | 2-5 min | Real from Google Maps | Production, actual lead gen |

## Recommendations

1. **Development**: Always use `mock=true` for fast iteration
2. **Testing**: Use `mock=false` with `limit=5` to test Apify integration
3. **Production**: Use `mock=false` with appropriate limits based on budget

## Next Steps

If issues persist:
1. Check `test_backend_discover.py` output
2. Review backend logs for Apify errors
3. Verify Apify account status and credits
4. Check network connectivity to Apify API
