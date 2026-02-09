# Implementation Tasks: Discover Leads Fix

## Overview

This task list tracks the implementation of the discover leads fix. Most code changes are already complete - the remaining work is service restarts and verification testing.

## Tasks

### Phase 1: Code Changes (COMPLETED ✅)

- [x] 1. Increase frontend timeout
  - [x] 1.1 Update `LONG_OPERATION_TIMEOUT_MS` in `frontend/lib/zrai/constants.ts`
  - Changed from 120000 (2 min) to 300000 (5 min)
  - _Requirements: 1.1, 1.4_

- [x] 2. Add mock mode to backend
  - [x] 2.1 Add `mock: bool` field to `DiscoverRequest` model in `src/api/server.py`
  - [x] 2.2 Implement mock data generation in `/api/v1/discover` endpoint
  - [x] 2.3 Add logging for mock mode
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Update frontend tool
  - [x] 3.1 Add `mock` parameter to `discoverLeads` tool schema
  - [x] 3.2 Set default `mock=true` for development
  - [x] 3.3 Add console logging for debugging
  - [x] 3.4 Improve error messages with suggestions
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 4. Update frontend API route
  - [x] 4.1 Add `mock` to request schema in `frontend/app/(chat)/api/zrai/discover/route.ts`
  - [x] 4.2 Pass `mock` parameter to backend
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 5. Create documentation
  - [x] 5.1 Create `FIX_SUMMARY_DISCOVER_LEADS.md`
  - [x] 5.2 Create `QUICK_START_AFTER_FIX.md`
  - [x] 5.3 Create `TROUBLESHOOTING_DISCOVER_LEADS.md`
  - [x] 5.4 Create `test_mock_discover.py`
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

### Phase 2: Service Restart (REQUIRED ⏳)

- [ ] 6. Restart backend service
  - [ ] 6.1 Stop current backend process (Ctrl+C in terminal running `python run.py`)
  - [ ] 6.2 Start backend: `python run.py`
  - [ ] 6.3 Verify startup: Look for "Application startup complete" message
  - [ ] 6.4 Verify health: `curl http://localhost:8000/health`
  - _Requirements: All - backend must be restarted to pick up code changes_

- [ ] 7. Restart frontend service
  - [ ] 7.1 Stop current frontend process (Ctrl+C in terminal running `pnpm dev`)
  - [ ] 7.2 Navigate to frontend: `cd frontend`
  - [ ] 7.3 Start frontend: `pnpm dev`
  - [ ] 7.4 Verify startup: Look for "Ready in X ms" message
  - _Requirements: All - frontend must be restarted to pick up code changes_

### Phase 3: Verification Testing (REQUIRED ⏳)

- [ ] 8. Test backend mock mode
  - [ ] 8.1 Run test script: `python test_mock_discover.py`
  - [ ] 8.2 Verify output shows "SUCCESS" with 10 mock leads
  - [ ] 8.3 Verify response time is < 1 second
  - _Requirements: 2.2, 3.2, 3.4_

- [ ] 9. Test frontend integration
  - [ ] 9.1 Open browser to http://localhost:3000
  - [ ] 9.2 Log in if required
  - [ ] 9.3 Select "Claude 3.5 Sonnet" from model dropdown
  - [ ] 9.4 Type: "Find me 20 SaaS leads in the US"
  - [ ] 9.5 Verify AI calls discoverLeads tool
  - [ ] 9.6 Verify leads appear in lead-list artifact
  - [ ] 9.7 Open browser DevTools → Console
  - [ ] 9.8 Verify `[discoverLeads]` log messages appear
  - _Requirements: 2.1, 4.4, 4.5, 6.1_

- [ ] 10. Test error handling
  - [ ] 10.1 Stop backend service
  - [ ] 10.2 Try "Find me 20 SaaS leads" in chat
  - [ ] 10.3 Verify helpful error message appears (not stack trace)
  - [ ] 10.4 Restart backend for further testing
  - _Requirements: 7.1, 7.4_

### Phase 4: Optional Real Mode Testing

- [ ] 11. Test real Apify mode (optional, takes 2-5 minutes)
  - [ ] 11.1 Ask: "Find me 5 real SaaS leads using Apify"
  - [ ] 11.2 Wait 2-5 minutes for real data
  - [ ] 11.3 Verify real company data appears
  - _Requirements: 2.3_

## Quick Commands Reference

```bash
# Terminal 1: Backend
python run.py

# Terminal 2: Frontend
cd frontend
pnpm dev

# Test mock mode
python test_mock_discover.py

# Check backend health
curl http://localhost:8000/health
```

## Success Criteria

✅ All Phase 1 tasks completed (code changes)
⏳ Phase 2: Services must be restarted
⏳ Phase 3: Verification tests must pass:
  - `test_mock_discover.py` returns SUCCESS
  - Browser test shows leads in artifact
  - Console logs show `[discoverLeads]` messages
  - No timeout errors

## Troubleshooting

If tests fail after restart:

1. **Backend not starting**: Check for Python errors, ensure all dependencies installed
2. **Frontend not starting**: Run `pnpm install` in frontend directory
3. **Mock mode not working**: Verify `src/api/server.py` has the mock code
4. **No leads in artifact**: Check browser console for errors, verify model supports tools
5. **Timeout errors**: Verify `LONG_OPERATION_TIMEOUT_MS` is 300000 in constants.ts

## Notes

- The user must manually restart both services - code changes don't auto-reload
- Use Claude 3.5 Sonnet for testing (not Gemini 2.0 Flash Lite)
- Mock mode is default for fast development iteration
- Real Apify mode available by explicitly requesting "real leads"
