# Testing the Model Compatibility Fix

## Quick Test Steps

### 1. Start Both Services

**Terminal 1 - Frontend:**
```bash
cd frontend
pnpm dev
```

**Terminal 2 - Backend:**
```bash
python run.py
```

Wait for both to start:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000

### 2. Test with Incapable Model (Should Show Warning)

1. Open http://localhost:3000
2. Click the model selector dropdown
3. Select **"Gemini 2.0 Flash Lite"**
4. Type: "Find me 20 SaaS leads in the US"
5. **Expected Result:**
   - ⚠️ Warning message appears in chat
   - AI explains that tools are disabled
   - AI recommends switching to Claude 3.5 Sonnet
   - **NO infinite loop**
   - **NO fake tool calls**

### 3. Test with Capable Model (Should Work Normally)

1. Click the model selector dropdown
2. Select **"Claude 3.5 Sonnet"**
3. Type: "Find me 20 SaaS leads in the US"
4. **Expected Result:**
   - Tool `discoverLeads` is called
   - Backend receives request at `/api/v1/discover`
   - Leads are returned and displayed
   - No warnings

### 4. Verify Backend Connectivity

```bash
# Test backend is responding
curl http://localhost:8000/api/v1/metrics

# Should return JSON with metrics
```

### 5. Check Console Logs

**Frontend Console (Browser DevTools):**
```
[OpenRouter] Creating model: google/gemini-2.0-flash-lite-001
[Chat API] Model "google/gemini-2.0-flash-lite-001" does not support tool calling...
```

**Backend Console:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

## Test Matrix

| Model | Tools Enabled? | Expected Behavior |
|-------|---------------|-------------------|
| Gemini 2.0 Flash Lite | ❌ No | Warning shown, regular chat only |
| Claude 3 Haiku | ❌ No | Warning shown, regular chat only |
| Claude 3.5 Sonnet | ✅ Yes | Tools work, backend called |
| GPT-4o | ✅ Yes | Tools work, backend called |
| Gemini 2.0 Flash | ✅ Yes | Tools work, backend called |
| Llama 3.2 3B | ❌ No | Warning shown, regular chat only |
| Llama 3.1 70B | ✅ Yes | Tools work, backend called |

## Troubleshooting

### Issue: Warning appears but I selected Claude 3.5 Sonnet
**Check:**
```bash
# Verify model ID in browser console
# Should see: [OpenRouter] Creating model: anthropic/claude-3.5-sonnet
```

### Issue: Tools still don't work with Claude 3.5 Sonnet
**Check backend:**
```bash
# Is backend running?
curl http://localhost:8000/api/v1/metrics

# Check backend logs for errors
```

### Issue: Infinite loop still happens
**Check:**
1. Did you restart the frontend dev server after changes?
2. Clear browser cache and reload
3. Check browser console for errors

## Success Criteria

✅ **Fix is working if:**
1. Gemini 2.0 Flash Lite shows warning and doesn't call tools
2. Claude 3.5 Sonnet calls tools successfully
3. No infinite loops with any model
4. Backend receives requests when using capable models
5. Console logs show appropriate warnings

❌ **Fix is NOT working if:**
1. Gemini 2.0 Flash Lite still causes infinite loops
2. Claude 3.5 Sonnet doesn't call tools
3. No warnings appear for incapable models
4. Backend never receives requests

## Next Steps After Testing

If tests pass:
1. ✅ Mark issue as resolved
2. 📝 Update CHANGELOG.md
3. 🚀 Deploy to production

If tests fail:
1. Check console logs for errors
2. Verify TypeScript compilation: `cd frontend && pnpm build`
3. Review MODEL_COMPATIBILITY_GUIDE.md for troubleshooting
