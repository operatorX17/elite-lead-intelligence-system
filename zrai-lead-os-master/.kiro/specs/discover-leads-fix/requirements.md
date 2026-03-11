# Requirements Document: Discover Leads Fix

## Introduction

This document defines the requirements for fixing the "Discover Leads Not Returning Data" issue in ZRAI Lead OS. The problem occurs when Claude 3.5 Sonnet (or other capable models) calls the `discoverLeads` tool but no leads appear in the response, despite the tool being invoked successfully.

## Problem Statement

Users report that when asking the AI to "Find me 20 SaaS leads", the AI correctly identifies and calls the `discoverLeads` tool, but no leads are displayed in the artifact. Investigation revealed multiple root causes:

1. **Timeout Mismatch**: Frontend timeout (2 min) < Backend Apify timeout (5 min)
2. **No Development Mode**: Real Apify scraping takes 2-5 minutes, making development/testing slow
3. **Poor Error Visibility**: No logging to diagnose where the request fails
4. **Model Compatibility**: Some models (Gemini 2.0 Flash Lite) don't properly support tool calling

## Glossary

- **Mock_Mode**: Development feature that returns instant fake data instead of real Apify scraping
- **Frontend_Timeout**: Maximum time the frontend waits for backend response (LONG_OPERATION_TIMEOUT_MS)
- **Backend_Timeout**: Maximum time the backend waits for Apify to return data
- **Tool_Calling**: AI capability to invoke functions/tools during conversation
- **Artifact**: Visual component displaying tool results (lead-list, lead-card, etc.)

---

## Requirements

### Requirement 1: Timeout Alignment

**User Story:** As a user, I want the frontend to wait long enough for real lead discovery, so that I receive actual leads instead of timeout errors.

#### Acceptance Criteria

1. THE Frontend_Timeout SHALL be at least equal to the Backend_Timeout (5 minutes)
2. WHEN the backend is processing a real Apify request, THE frontend SHALL wait the full timeout period
3. IF the request times out, THEN THE system SHALL return a clear error message explaining the timeout
4. THE timeout configuration SHALL be centralized in `frontend/lib/zrai/constants.ts`

---

### Requirement 2: Mock Mode for Development

**User Story:** As a developer, I want instant mock data for testing, so that I can iterate quickly without waiting for real Apify scraping.

#### Acceptance Criteria

1. THE `discoverLeads` tool SHALL accept a `mock` boolean parameter
2. WHEN `mock=true`, THE backend SHALL return fake lead data instantly (< 1 second)
3. WHEN `mock=false`, THE backend SHALL use real Apify scraping (2-5 minutes)
4. THE mock data SHALL include realistic company names, domains, and contact info
5. THE mock data SHALL respect the `limit` parameter
6. THE mock mode SHALL be the default in development for faster iteration
7. THE mock response SHALL have the same schema as real responses

---

### Requirement 3: Backend Mock Implementation

**User Story:** As a backend developer, I want the mock mode implemented in the FastAPI server, so that the frontend can request instant test data.

#### Acceptance Criteria

1. THE `DiscoverRequest` model SHALL include a `mock: bool` field with default `False`
2. WHEN `mock=true` is received, THE `/api/v1/discover` endpoint SHALL bypass Apify
3. THE mock data generator SHALL create leads with:
   - Unique UUIDs for `id`
   - Company names based on the requested `niche`
   - Realistic domains (e.g., `company1.com`)
   - Contact emails matching the domain
   - Correct `niche` and `geo` values from the request
4. THE mock response SHALL include `leads`, `count`, and `run_id` fields
5. THE backend SHALL log when mock mode is used for debugging

---

### Requirement 4: Frontend Tool Integration

**User Story:** As a frontend developer, I want the discoverLeads tool to pass the mock parameter to the backend, so that users can choose between fast mock data and real scraping.

#### Acceptance Criteria

1. THE `discoverLeads` tool SHALL include `mock` in its input schema
2. THE tool SHALL default `mock=true` for development convenience
3. THE tool SHALL pass the `mock` parameter to the backend API
4. THE tool SHALL log the request parameters for debugging
5. THE tool SHALL log the response status and lead count
6. IF the backend returns an error, THEN THE tool SHALL return a helpful error message with suggestions

---

### Requirement 5: Frontend API Route Pass-Through

**User Story:** As a frontend developer, I want the API route to pass the mock parameter to the backend, so that the full request chain supports mock mode.

#### Acceptance Criteria

1. THE `/api/zrai/discover` route SHALL accept `mock` in the request body
2. THE route SHALL pass `mock` to the backend `/api/v1/discover` endpoint
3. THE route SHALL log errors with sufficient detail for debugging
4. THE route SHALL handle backend errors gracefully with appropriate HTTP status codes

---

### Requirement 6: Logging and Debugging

**User Story:** As a developer, I want comprehensive logging throughout the discover flow, so that I can diagnose issues quickly.

#### Acceptance Criteria

1. THE `discoverLeads` tool SHALL log: request start, parameters, response status, lead count
2. THE backend `/api/v1/discover` endpoint SHALL log: request received, mock mode status, lead count returned
3. THE frontend API route SHALL log: errors with status codes and messages
4. ALL logs SHALL use consistent prefixes for easy filtering (e.g., `[discoverLeads]`, `[ZRAI:discover]`)

---

### Requirement 7: Error Handling and User Guidance

**User Story:** As a user, I want clear error messages when discovery fails, so that I know what went wrong and how to fix it.

#### Acceptance Criteria

1. IF the backend is not running, THEN THE tool SHALL suggest checking if the backend is running on port 8000
2. IF the request times out, THEN THE tool SHALL suggest using mock mode for testing
3. IF authentication fails, THEN THE tool SHALL indicate the user needs to log in
4. THE error messages SHALL be user-friendly, not technical stack traces

---

### Requirement 8: Documentation

**User Story:** As a developer, I want clear documentation of the fix, so that I can understand and maintain the solution.

#### Acceptance Criteria

1. THE fix SHALL be documented in `FIX_SUMMARY_DISCOVER_LEADS.md`
2. THE documentation SHALL include: problem description, root cause, changes made, testing steps
3. A quick start guide SHALL be provided in `QUICK_START_AFTER_FIX.md`
4. A troubleshooting guide SHALL be provided in `TROUBLESHOOTING_DISCOVER_LEADS.md`
5. A test script SHALL be provided in `test_mock_discover.py`

---

## Implementation Status

### Completed ✅

1. **Timeout Alignment** (Requirement 1)
   - Changed `LONG_OPERATION_TIMEOUT_MS` from 120000 to 300000 in `frontend/lib/zrai/constants.ts`

2. **Backend Mock Implementation** (Requirement 3)
   - Added `mock: bool` to `DiscoverRequest` in `src/api/server.py`
   - Implemented mock data generation that returns instantly

3. **Frontend Tool Integration** (Requirement 4)
   - Added `mock` parameter to `discoverLeads` tool in `frontend/lib/ai/tools/zrai/discover-leads.ts`
   - Added logging throughout the tool

4. **Frontend API Route Pass-Through** (Requirement 5)
   - Updated `frontend/app/(chat)/api/zrai/discover/route.ts` to pass `mock` parameter

5. **Logging and Debugging** (Requirement 6)
   - Added console.log statements with `[discoverLeads]` prefix

6. **Documentation** (Requirement 8)
   - Created `FIX_SUMMARY_DISCOVER_LEADS.md`
   - Created `QUICK_START_AFTER_FIX.md`
   - Created `TROUBLESHOOTING_DISCOVER_LEADS.md`
   - Created `test_mock_discover.py`

### Pending ⏳

1. **Service Restart Required**
   - Backend must be restarted to pick up new mock mode code
   - Frontend must be restarted to pick up new timeout and tool changes

2. **Testing**
   - Run `python test_mock_discover.py` to verify backend mock mode
   - Test in browser with Claude 3.5 Sonnet: "Find me 20 SaaS leads"
   - Verify leads appear in artifact

---

## Testing Checklist

- [ ] Backend restarted with `python run.py`
- [ ] Frontend restarted with `cd frontend && pnpm dev`
- [ ] `python test_mock_discover.py` returns mock leads instantly
- [ ] Browser test: "Find me 20 SaaS leads" shows leads in artifact
- [ ] Console logs show `[discoverLeads]` messages
- [ ] No timeout errors occur

---

## Files Modified

| File | Change |
|------|--------|
| `frontend/lib/zrai/constants.ts` | Timeout: 2min → 5min |
| `src/api/server.py` | Added mock mode to DiscoverRequest and endpoint |
| `frontend/lib/ai/tools/zrai/discover-leads.ts` | Added mock param, logging |
| `frontend/app/(chat)/api/zrai/discover/route.ts` | Pass through mock param |

## Files Created

| File | Purpose |
|------|---------|
| `FIX_SUMMARY_DISCOVER_LEADS.md` | Complete fix documentation |
| `QUICK_START_AFTER_FIX.md` | Quick testing guide |
| `TROUBLESHOOTING_DISCOVER_LEADS.md` | Troubleshooting guide |
| `test_mock_discover.py` | Backend mock mode test script |
