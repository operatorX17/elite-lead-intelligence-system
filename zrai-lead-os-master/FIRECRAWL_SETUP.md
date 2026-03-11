# Firecrawl Setup Guide

## What is Firecrawl?

Firecrawl is a cloud-based web scraping service that:
- Runs in the cloud (no local browser needed)
- Handles JavaScript rendering
- Returns clean HTML/Markdown
- Has generous free tier (500 credits/month)
- Much simpler than Steel API

## Why Switch from Steel to Firecrawl?

**Steel Issues:**
- API key works in MCP but NOT in REST API
- Different authentication mechanisms
- Complex WebSocket setup
- 401 Unauthorized errors

**Firecrawl Benefits:**
- Simple REST API
- Works immediately
- Free tier available
- No authentication issues
- Cloud-based (fast)

## Setup Steps

### 1. Get Firecrawl API Key

1. Go to https://firecrawl.dev
2. Click "Sign Up" (free account)
3. Verify your email
4. Go to Dashboard → API Keys
5. Copy your API key (starts with `fc-`)

### 2. Add to .env

Open `.env` and update:

```bash
FIRECRAWL_API_KEY=fc-your-actual-api-key-here
```

### 3. Test Integration

Run the test script:

```bash
python test_firecrawl_direct.py
```

Expected output:
```
✓ API key found: fc-xxx...

Testing: Redcliffe Labs
URL: https://www.redcliffelabs.com/

Status: firecrawl_success
Booking System: True
WhatsApp: True
Lead Form: True
Click-to-Call: True
Chat Widget: False
Emails: ['info@redcliffelabs.com']
Phones: ['+918988988787']

✅ FIRECRAWL WORKING!
```

### 4. Run Full Pipeline

Once Firecrawl is working, run the full pipeline:

```bash
python lead_os.py --city Bangalore --n 50 --niche diagnostics
```

This will:
1. Discover 50 leads from Google Maps (Apify)
2. Enrich with Firecrawl (cloud scraping)
3. Score leads (0-100)
4. Generate outreach messages
5. Export CSV + JSON

## Pricing

**Free Tier:**
- 500 credits/month
- 1 credit = 1 page scrape
- Perfect for testing

**Paid Plans:**
- Starter: $29/month (5,000 credits)
- Growth: $99/month (25,000 credits)
- Scale: $299/month (100,000 credits)

For 500 leads/day:
- 500 scrapes/day = 15,000/month
- Need Growth plan ($99/month)
- Still cheaper than Steel!

## API Endpoints

Firecrawl REST API:
```
POST https://api.firecrawl.dev/v1/scrape
Authorization: Bearer fc-xxx
Content-Type: application/json

{
  "url": "https://example.com",
  "formats": ["markdown", "html"],
  "onlyMainContent": true,
  "waitFor": 2000
}
```

Response:
```json
{
  "success": true,
  "data": {
    "markdown": "# Page content...",
    "html": "<html>...</html>",
    "metadata": {
      "title": "Page Title",
      "description": "..."
    }
  }
}
```

## Troubleshooting

### Error: "No API key found"
- Check `.env` has `FIRECRAWL_API_KEY=fc-xxx`
- Restart terminal to reload environment
- Run `python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('FIRECRAWL_API_KEY'))"`

### Error: "401 Unauthorized"
- API key is invalid
- Get new key from https://firecrawl.dev/dashboard
- Make sure no extra spaces in `.env`

### Error: "429 Too Many Requests"
- Free tier limit reached (500/month)
- Upgrade to paid plan
- Or wait until next month

### Fallback Mode
If Firecrawl fails, the system uses URL heuristics:
- Checks if URL contains "practo", "calendly", etc.
- Less accurate but prevents pipeline failure
- Shows `status: fallback` in output

## Next Steps

Once Firecrawl is working:

1. **Test with 10 leads:**
   ```bash
   python lead_os.py --city Bangalore --n 10 --niche diagnostics
   ```

2. **Verify enrichment quality:**
   - Check `output/Bangalore_diagnostics_*/Bangalore_500_leads.csv`
   - Look for `status: firecrawl_success`
   - Verify signals are accurate

3. **Scale to 500 leads:**
   ```bash
   python lead_os.py --city Bangalore --n 500 --niche mixed
   ```

4. **Burn through credits:**
   - Run multiple niches
   - Process 500 leads/day
   - Generate hot leads with proof

## Support

- Firecrawl Docs: https://docs.firecrawl.dev
- Firecrawl Discord: https://discord.gg/firecrawl
- API Status: https://status.firecrawl.dev

## Comparison: Steel vs Firecrawl

| Feature | Steel | Firecrawl |
|---------|-------|-----------|
| Authentication | Complex (MCP works, REST fails) | Simple (Bearer token) |
| Setup | Multiple methods (SDK, CLI, Playwright) | Single REST API |
| Pricing | $0.10/hour (3000 hours = $300) | $99/month (25k credits) |
| Speed | Slower (full browser) | Faster (optimized) |
| Reliability | WebSocket issues | Stable REST API |
| Use Case | Interactive browsing | Static scraping |

**Verdict:** Firecrawl is better for Lead OS enrichment.

---

**Status:** Ready to use once API key is added to `.env`
