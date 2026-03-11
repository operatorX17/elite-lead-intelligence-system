# Quick Start After Fix

## 🚀 3 Steps to Get Leads Working

### 1. Restart Backend
```bash
# Terminal 1
python run.py
```
Wait for: `INFO: Application startup complete.`

### 2. Restart Frontend
```bash
# Terminal 2
cd frontend
pnpm dev
```
Wait for: `Ready in X ms`

### 3. Test in Browser
1. Open http://localhost:3000
2. Select **Claude 3.5 Sonnet** (not Gemini Lite!)
3. Ask: **"Find me 20 SaaS leads in the US"**
4. ✅ Leads should appear instantly!

## ⚡ What Changed?

- **Timeout**: 2 min → 5 min (frontend now waits longer)
- **Mock Mode**: Added instant test data (default in dev)
- **Logging**: Better error messages in console
- **Model Check**: Tools disabled for weak models

## 🐛 Still Not Working?

### Quick Checks
```bash
# Backend alive?
curl http://localhost:8000/health

# Mock mode working?
python test_mock_discover.py

# Frontend alive?
curl http://localhost:3000
```

### Common Issues

| Problem | Solution |
|---------|----------|
| No leads appear | Restart both services |
| Timeout error | Check backend is running |
| "Tools disabled" warning | Switch to Claude 3.5 Sonnet |
| 401 error | Log in to frontend |

## 📖 Full Documentation

- `FIX_SUMMARY_DISCOVER_LEADS.md` - Complete fix details
- `TROUBLESHOOTING_DISCOVER_LEADS.md` - Detailed troubleshooting
- `MODEL_COMPATIBILITY_GUIDE.md` - Model capabilities

## 🎯 Expected Result

```
You: "Find me 20 SaaS leads"

AI: "I'll use the discoverLeads tool to find 20 SaaS companies..."

[Instant response]

AI: "Here are 20 SaaS leads I've discovered in the US..."

[Lead-list artifact appears with companies]
```

## 💡 Pro Tips

- **Fast Testing**: Mock mode is default (instant)
- **Real Data**: Ask "find real leads using Apify" (2-5 min)
- **Best Model**: Claude 3.5 Sonnet works best
- **Check Logs**: Open browser console for debugging
