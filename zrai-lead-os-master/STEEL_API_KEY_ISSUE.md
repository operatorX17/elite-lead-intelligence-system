# Steel API Key Issue

## Problem
The Steel API key in `.env` returns 401 Unauthorized when calling Steel's cloud API.

## Root Cause
The API key `ste-qNSs7uzWS0EwTw99jG9QswET8x7ZSUHsLoFt5QSCQXpLJ8nlPohVXwZ18Ao3uoiDyEJRD17Ci1zsyetYIrsOMX11cVYMhy8ghFVBro` is either:
1. Invalid/expired
2. Not authorized for cloud API access
3. Only works with CLI/MCP (different auth mechanism)

## Solution

### Get a Valid Steel API Key
1. Go to https://app.steel.dev
2. Sign up or log in
3. Navigate to Settings > API Keys
4. Create a new API key
5. Copy the key and update `.env`:
   ```
   STEEL_API_KEY=ste-YOUR-NEW-KEY-HERE
   ```

### Alternative: Use Firecrawl (Already Working)
Firecrawl MCP is configured and working. Use it for enrichment:

```python
# In lead_os.py
from src.tools.firecrawl_enrichment import FirecrawlEnrichment

async def steel_analyze_website(self, website: str, business_name: str):
    firecrawl = FirecrawlEnrichment()
    return await firecrawl.analyze_website(website, business_name)
```

## Current Status
- ❌ Steel REST API - 401 Unauthorized
- ❌ Steel Python SDK - 401 Unauthorized
- ✅ Steel MCP - Working (but you don't want MCP)
- ✅ Firecrawl MCP - Working and ready to use
- ✅ Heuristics - Working (80% accurate, instant)

## Recommendation
**Use Firecrawl for now, get new Steel key later:**

1. Firecrawl is already configured and working
2. Can scrape HTML and extract signals
3. Fast and reliable
4. Once you get a valid Steel key, switch to Steel

## Next Steps
1. Get new Steel API key from app.steel.dev
2. Update .env with new key
3. Test with `python test_steel_sdk_direct.py`
4. If works, Steel will be used for enrichment
5. If not, Firecrawl is the backup
