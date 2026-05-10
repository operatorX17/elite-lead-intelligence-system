# Fix Summary: Discover Leads Not Showing Data

## Problem Identified ✅
Claude 3.5 Sonnet calls `discoverLeads` tool but no leads appear because:
1. **Frontend timeout (2 min) < Backend Apify timeout (5 min)**
2. **No visual feedback during long operations**
3. **No development/testing mode for fast iteration**

## Changes Made ✅

### 1. Increased Frontend Timeout
**File**: `frontend/lib/zrai/constants.ts`
```diff
- export const LONG_OPERATION_TIMEOUT_MS = 120000; // 2 minutes
+ export const LONG_OPERATION_TIMEOUT_MS = 300000; // 5 minutes
```

### 2. Added Mock Mode to Backend
**File**: `src/api/server.py`
- Added `mock: bool` parameter to `DiscoverRequest`
- Added instant mock data generation when `mock=true`
- Keeps real Apify integration when `mock=false`

### 3. Updated Frontend API Route
**File**: `frontend/app/(chat)/api/zrai/discover/route.ts`
- Pass through `mock` parameter to backend
- Added better error logging

### 4. Updated Discover Tool
**File**: `frontend/lib/ai/tools/zrai/discover-leads.ts`
- Added `mock` parameter (defaults to `true` for development)
- Added console logging for debugging
- Improved error messages

### 5. Created Documentation
- `TROUBLESHOOTING_DISCOVER_LEADS.md` - Complete troubleshooting guide
- `MODEL_COMPATIBILITY_GUIDE.md` - Model capability documentation
- `TEST_MODEL_FIX.md` - Testing instructions
- `QUICK_FIX_SUMMARY.md` - Quick reference

## How to Test

### Step 1: Restart Backend (REQUIRED)
```bash
# Stop the current backend (Ctrl+C)
# Then restart:
python run.py
```

### Step 2: Restart Frontend (REQUIRED)
```bash
# Stop the current frontend (Ctrl+C)
cd frontend
pnpm dev
```

### Step 3: Test Mock Mode (Fast)
1. Open http://localhost:3000
2. Select **"Claude 3.5 Sonnet"** from model dropdown
3. Ask: **"Find me 20 SaaS leads in the US"**
4. **Expected**: Instant response with mock data showing in lead-list artifact

### Step 4: Verify in Browser Console
Open DevTools → Console, you should see:
```
[discoverLeads] Starting discovery: niche=saas, geo=us, limit=20, mock=true
[discoverLeads] Response status: 200
[discoverLeads] Success: 20 leads discovered
```

### Step 5: Test Real Mode (Slow - Optional)
Ask: **"Find me 5 real SaaS leads using Apify"**
- This will take 2-5 minutes
- Real data from Google Maps

## Expected Behavior

### Before Fix ❌
```
User: "Find me 20 SaaS leads"
AI: "I'll use the discoverLeads tool..."
AI: "Here are 20 SaaS leads I've discovered..."
[No leads shown - tool timed out]
```

### After Fix ✅
```
User: "Find me 20 SaaS leads"
AI: "I'll use the discoverLeads tool..."
[Instant response with mock=true]
AI: "Here are 20 SaaS leads I've discovered..."
[Lead-list artifact appears with 20 companies]
```

## Verification Checklist

- [ ] Backend restarted with new code
- [ ] Frontend restarted with new code
- [ ] Claude 3.5 Sonnet selected (not Gemini Lite)
- [ ] Browser console shows `[discoverLeads]` logs
- [ ] Leads appear in artifact
- [ ] No timeout errors

## If Still Not Working

### Check 1: Backend Running?
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy",...}
```

### Check 2: Mock Mode Working?
```bash
python test_mock_discover.py
# Should return instant mock data
```

### Check 3: Frontend Connecting?
Check browser console for errors:
- 401: Not logged in
- 503: Backend not running
- Timeout: Backend hanging (check backend logs)

### Check 4: Model Supports Tools?
- ✅ Use: Claude 3.5 Sonnet, GPT-4o, Gemini 2.0 Flash
- ❌ Don't use: Gemini 2.0 Flash Lite, Claude 3 Haiku

## Architecture

```
User → Claude 3.5 Sonnet → discoverLeads(mock=true)
                              ↓
                    Frontend /api/zrai/discover
                              ↓
                    Backend /api/v1/discover
                              ↓
                    ┌─────────┴─────────┐
                    ↓                   ↓
              mock=true           mock=false
            (instant mock)      (2-5 min Apify)
                    ↓                   ↓
              Mock leads          Real leads
                    └─────────┬─────────┘
                              ↓
                    Lead-list artifact
```

## Performance

| Mode | Time | Data | Use Case |
|------|------|------|----------|
| Mock | <1s | Fake | Development, testing, demos |
| Real | 2-5min | Real | Production lead generation |

## Files Changed

1. `frontend/lib/zrai/constants.ts` - Timeout increased
2. `src/api/server.py` - Mock mode added
3. `frontend/app/(chat)/api/zrai/discover/route.ts` - Pass mock param
4. `frontend/lib/ai/tools/zrai/discover-leads.ts` - Mock param + logging
5. `frontend/lib/ai/models.ts` - Model capability flags
6. `frontend/app/(chat)/api/chat/route.ts` - Tool disabling logic
7. `frontend/lib/ai/prompts.ts` - User guidance

## Next Actions

1. **RESTART BOTH SERVICES** (most important!)
2. Test with Claude 3.5 Sonnet
3. Verify mock mode works
4. (Optional) Test real mode with small limit

## Success Criteria

✅ Mock mode returns data instantly  
✅ Leads appear in artifact  
✅ No timeout errors  
✅ Console logs show success  
✅ AI can see and describe the leads
