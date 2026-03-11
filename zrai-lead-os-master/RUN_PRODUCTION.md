# 🚀 RUN PRODUCTION - LEAD OS v1.0

## Quick Start

### Test Run (10 leads - DONE ✅)
```bash
python test_lead_os.py
```

**Results**: 2 HOT, 2 WARM, 5 COLD from 9 leads

---

## Production Runs

### 1. Bangalore Mixed (500 leads)
```bash
python lead_os.py --city "Bangalore" --n 500 --niche "mixed"
```

**Expected**:
- 500 leads discovered
- 100-150 HOT leads (70+ score)
- 100-150 WARM leads (50-69 score)
- 200-300 outreach messages ready
- Time: ~2-3 hours

### 2. Bangalore Diagnostics Only
```bash
python lead_os.py --city "Bangalore" --n 500 --niche "diagnostics"
```

### 3. Bangalore Dental Only
```bash
python lead_os.py --city "Bangalore" --n 500 --niche "dental"
```

### 4. Bangalore Skin Clinics
```bash
python lead_os.py --city "Bangalore" --n 500 --niche "skin"
```

### 5. Bangalore IVF Centers
```bash
python lead_os.py --city "Bangalore" --n 500 --niche "ivf"
```

### 6. Bangalore Physiotherapy
```bash
python lead_os.py --city "Bangalore" --n 500 --niche "physio"
```

### 7. Bangalore Multi-speciality
```bash
python lead_os.py --city "Bangalore" --n 500 --niche "multispeciality"
```

---

## Other Cities

### Mumbai
```bash
python lead_os.py --city "Mumbai" --n 500 --niche "mixed"
```

### Delhi
```bash
python lead_os.py --city "Delhi" --n 500 --niche "mixed"
```

### Hyderabad
```bash
python lead_os.py --city "Hyderabad" --n 500 --niche "mixed"
```

### Chennai
```bash
python lead_os.py --city "Chennai" --n 500 --niche "mixed"
```

### Pune
```bash
python lead_os.py --city "Pune" --n 500 --niche "mixed"
```

---

## Output Files

After each run, check:
```
output/[City]_[niche]_[timestamp]/
├── [City]_500_leads.csv          # All leads
├── top50_hot_leads.json          # HOT leads with outreach
└── run_report.json               # Statistics
```

---

## What You Get

### For Each HOT Lead:
- ✅ Business name, category, location
- ✅ Website, phone, email
- ✅ Booking system detection
- ✅ WhatsApp detection
- ✅ Lead form detection
- ✅ Leak score (70-100)
- ✅ Money estimate (₹ loss/month)
- ✅ Recoverable amount
- ✅ Recommended tier (Basic/Pro/Elite)
- ✅ ROI multiple
- ✅ Email subject + body
- ✅ WhatsApp message
- ✅ Call script
- ✅ Loom script

---

## Scoring Thresholds

- **HOT (70-100)**: Real data + Reachable + Active business + Clear opportunity
- **WARM (50-69)**: Some real data + Reachable + Moderate opportunity
- **COLD (30-49)**: Fallback data OR Unreachable OR No opportunity
- **DISQUALIFIED (0-29)**: No website, no contact info, or rejected by AI

---

## Cost Estimates

### Apify (Google Maps Discovery)
- $5 budget = ~500-1000 leads
- Cost per lead: ~$0.005-0.01

### Firecrawl (Website Enrichment)
- Free tier: 500 scrapes/month
- Paid: $0.01-0.02 per scrape
- Cost for 500 leads: ~$5-10

### OpenRouter (AI Reasoning)
- Kimi K2:free model = FREE
- Cost: $0

**Total Cost for 500 Leads**: ~$5-15

---

## Time Estimates

- Discovery (Apify): 5-10 minutes
- Enrichment (Firecrawl): 1-2 hours (parallel batches)
- AI Reasoning: 10-20 minutes
- Money Estimates: 1 minute
- Outreach Generation: 5 minutes
- Export: 1 minute

**Total Time**: ~2-3 hours for 500 leads

---

## Monitoring

Watch the console for:
- ✅ Green checkmarks = success
- ⚠️ Yellow warnings = non-critical issues
- ❌ Red errors = critical failures

The system will:
- Auto-retry failed enrichments
- Skip unreachable leads
- Continue processing even if some leads fail
- Save all results to database

---

## Next Steps After Run

1. **Review HOT leads** in `top50_hot_leads.json`
2. **Send outreach** using generated messages
3. **Track responses** in your CRM
4. **Schedule calls** with interested leads
5. **Close deals** and collect ₹60k-120k/month

---

## Troubleshooting

### If enrichment fails:
- Check Firecrawl API key in `.env`
- Check internet connection
- Some websites may timeout (normal, system continues)

### If scoring seems off:
- Check `src/agents/reasoning.py` for scoring logic
- Adjust thresholds in `lead_os.py` if needed

### If no HOT leads:
- Lower threshold from 70 to 60 in `lead_os.py`
- Or increase opportunity scoring in `src/agents/reasoning.py`

---

## Support

Check these files for details:
- `SCORING_FIX_SUCCESS.md` - What changed and why
- `SCORING_FIX_SUMMARY.md` - Technical details
- `lead_os.py` - Main pipeline code
- `src/agents/reasoning.py` - AI reasoning logic

---

**Ready to run?**
```bash
python lead_os.py --city "Bangalore" --n 500 --niche "mixed"
```

**Goal**: ₹5L/month in 30 days
**Path**: 500 leads → 100 HOT → 20 conversations → 6 calls → 2-3 closes → ₹120-180k/month (week 1)
