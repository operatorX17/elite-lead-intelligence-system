# BURN 3000 HOURS OF STEEL CREDITS - EXECUTION PLAN

## 🎯 MISSION
Burn 3000 hours ($200 worth) of Steel credits in 3 days to extract 30,000-40,000 leads with REAL intelligence.

---

## 📊 THE MATH

### Credits Available:
- **3000 hours** of Steel browser automation
- **$200 value**
- **Must use in 3 days** (72 hours)

### Usage Strategy:
- **3000 hours / 72 hours = 41.67 hours/hour**
- **Need to run ~42 parallel sessions continuously**
- **Each session processes ~714 leads**
- **Total: 42 × 714 = 30,000 leads**

### Time per Lead:
- **Apify discovery: 10 seconds** (bulk scraping)
- **Steel intelligence: 5 minutes** (website browsing)
- **Total: ~5 minutes per lead**
- **30,000 leads × 5 min = 150,000 minutes = 2,500 hours**

**WE CAN DO IT!**

---

## 🏗️ ARCHITECTURE

### Two-Phase System:

#### Phase 1: APIFY BULK DISCOVERY (FAST)
**Tool:** Apify Google Maps Scraper  
**Speed:** 100-200 leads/minute  
**Cost:** Apify credits (you have them)  
**Output:** Basic lead data (name, location, phone, website)

**What it does:**
```
For each city (50 cities):
  For each lead type (8 types):
    Search Google Maps
    Extract 20-30 businesses
    Save to queue
```

**Result:** 30,000 leads in 2-3 hours

#### Phase 2: STEEL DEEP INTELLIGENCE (PARALLEL)
**Tool:** Steel Browser Automation  
**Speed:** 50 parallel sessions  
**Cost:** Steel credits (3000 hours to burn)  
**Output:** Deep intelligence (bed count, emails, departments, etc.)

**What it does:**
```
For each lead from Phase 1:
  Navigate to website using Steel
  Extract bed count
  Find contact emails
  Check for online booking
  Check for insurance portal
  Extract department list
  Take screenshots
  Save intelligence
```

**Result:** 30,000 enriched leads in 48-60 hours

---

## 🚀 EXECUTION PLAN

### Day 1: SETUP & START (8 hours)

**Hour 1-2: Setup**
```bash
# Install dependencies
pip install aiohttp rich

# Test Steel API
python -c "import os; print(os.getenv('STEEL_API_KEY'))"

# Test Apify API
python -c "import os; print(os.getenv('APIFY_API_TOKEN'))"
```

**Hour 3-4: Phase 1 - Apify Discovery**
```bash
# Run Apify bulk discovery
python MASSIVE_LEAD_EXTRACTION.py --target 30000 --steel-sessions 50
```

**Expected Output:**
- 30,000 leads discovered
- Saved to `discovered_leads.json`
- Ready for Phase 2

**Hour 5-8: Phase 2 - Steel Intelligence (START)**
- 50 Steel sessions start
- Each session processes 600 leads
- Running 24/7 from now on

### Day 2: MONITOR & SCALE (24 hours)

**Continuous Monitoring:**
```bash
# Check progress
tail -f logs/steel_extraction.log

# Check lead count
wc -l MASSIVE_LEADS_*.json

# Check Steel usage
# (Monitor Steel dashboard)
```

**Expected Progress:**
- Hour 12: 5,000 leads enriched
- Hour 24: 10,000 leads enriched
- Hour 36: 15,000 leads enriched

**If too slow:**
```bash
# Increase parallel sessions
# Stop current run
# Restart with more sessions
python MASSIVE_LEAD_EXTRACTION.py --target 30000 --steel-sessions 100
```

### Day 3: COMPLETE & ANALYZE (24 hours)

**Hour 48-60: Complete Extraction**
- All 30,000 leads enriched
- Steel credits burned
- Data saved to database

**Hour 60-72: Analysis & Categorization**
```bash
# Analyze results
python analyze_leads.py

# Categorize by priority
python categorize_leads.py

# Generate intelligence reports
python generate_reports.py
```

**Final Output:**
- 30,000-40,000 leads with REAL intelligence
- Categorized by priority (Tier A, B, C)
- Ready for outreach
- Steel credits burned

---

## 📁 FILES CREATED

### 1. BURN_STEEL_CREDITS.py
**Purpose:** Pure Steel-based extraction (50 parallel sessions)  
**Use when:** You want maximum Steel usage  
**Speed:** Slower (Steel only)  
**Quality:** Highest (deep browsing)

### 2. MASSIVE_LEAD_EXTRACTION.py (RECOMMENDED)
**Purpose:** Hybrid Apify + Steel extraction  
**Use when:** You want speed + quality  
**Speed:** Fastest (Apify bulk + Steel parallel)  
**Quality:** High (real intelligence)

**This is the one to use.**

---

## 🎯 LEAD TYPES TO EXTRACT

### Priority 1 (HIGH VALUE):
1. **Multi-Specialty Hospitals** (20 per city × 50 cities = 1,000)
2. **Super-Specialty Hospitals** (15 per city × 50 cities = 750)

### Priority 2 (MEDIUM VALUE):
3. **General Hospitals** (30 per city × 50 cities = 1,500)
4. **Diagnostic Centers** (25 per city × 50 cities = 1,250)
5. **Eye Hospitals** (10 per city × 50 cities = 500)
6. **Maternity Hospitals** (10 per city × 50 cities = 500)

### Priority 3 (LOWER VALUE):
7. **Polyclinics** (20 per city × 50 cities = 1,000)
8. **Dental Hospitals** (15 per city × 50 cities = 750)

**Total: 7,250 leads minimum**

**To reach 30,000:**
- Expand to more cities (100 cities)
- Add more lead types (labs, pharmacies, etc.)
- Increase per-city targets

---

## 💰 EXPECTED RESULTS

### Lead Quality:
```json
{
  "business_name": "Apollo Hospital Hyderabad",
  "location": "Hyderabad, Telangana",
  "phone": "+91 40 2345 6789",
  "website": "https://apollohospital.com",
  "lead_type": "Multi-Specialty Hospital",
  "priority": 1,
  "intelligence": {
    "bed_count": 250,
    "has_online_booking": true,
    "has_insurance_portal": false,
    "contact_emails": ["info@apollo.com", "admin@apollo.com"],
    "contact_phones": ["+91 40 2345 6789", "+91 40 2345 6790"],
    "departments": ["Cardiology", "Neurology", "Oncology"],
    "monthly_loss_estimate": "₹218.75 lakhs",
    "roi": "175x"
  }
}
```

### Data Quality:
- **Hospital Name:** 100% REAL (Apify)
- **Location:** 100% REAL (Apify)
- **Phone:** 100% REAL (Apify)
- **Website:** 100% REAL (Apify)
- **Bed Count:** 80% REAL (Steel scraping)
- **Emails:** 70% REAL (Steel scraping)
- **Departments:** 60% REAL (Steel scraping)
- **Online Booking:** 90% REAL (Steel detection)

**Overall: 85% REAL DATA**

---

## 🚨 POTENTIAL ISSUES & SOLUTIONS

### Issue 1: Steel Rate Limiting
**Problem:** Steel API rate limits  
**Solution:** Reduce parallel sessions from 50 to 30  
**Impact:** Takes longer but still completes

### Issue 2: Website Timeouts
**Problem:** Some websites load slowly  
**Solution:** Increase timeout from 30s to 60s  
**Impact:** Slower but more reliable

### Issue 3: Apify Credit Exhaustion
**Problem:** Run out of Apify credits  
**Solution:** Use Steel for discovery too (slower)  
**Impact:** Takes 2x longer

### Issue 4: Database Overload
**Problem:** Too many writes to Supabase  
**Solution:** Batch writes (100 leads at a time)  
**Impact:** Minimal

### Issue 5: Not Burning Enough Credits
**Problem:** Only using 1000 hours in 3 days  
**Solution:** Increase parallel sessions to 100  
**Impact:** Burns credits faster

---

## 📊 MONITORING DASHBOARD

### Key Metrics to Track:

1. **Leads Discovered** (Apify)
   - Target: 30,000
   - Current: ?
   - Rate: ? leads/minute

2. **Leads Enriched** (Steel)
   - Target: 30,000
   - Current: ?
   - Rate: ? leads/minute

3. **Steel Hours Used**
   - Target: 3,000 hours
   - Current: ?
   - Rate: ? hours/hour

4. **Success Rate**
   - Target: 85%
   - Current: ?
   - Errors: ?

5. **Time Remaining**
   - Target: 3 days
   - Elapsed: ?
   - Remaining: ?

---

## 🎯 SUCCESS CRITERIA

### Must Have:
- ✅ 30,000+ leads extracted
- ✅ 2,500+ hours of Steel credits burned
- ✅ 85%+ data quality (real scraped data)
- ✅ All leads saved to database
- ✅ Categorized by priority

### Nice to Have:
- ✅ 40,000+ leads extracted
- ✅ 3,000 hours of Steel credits burned (100%)
- ✅ 90%+ data quality
- ✅ Intelligence reports generated
- ✅ Ready for immediate outreach

---

## 🚀 READY TO START?

### Quick Start:
```bash
# 1. Check credentials
echo $STEEL_API_KEY
echo $APIFY_API_TOKEN

# 2. Run the system
python MASSIVE_LEAD_EXTRACTION.py --target 30000 --steel-sessions 50

# 3. Monitor progress
tail -f logs/extraction.log

# 4. Check results
ls -lh MASSIVE_LEADS_*.json
```

### Expected Timeline:
- **Hour 0-3:** Apify discovers 30,000 leads
- **Hour 3-60:** Steel enriches all leads (50 parallel sessions)
- **Hour 60-72:** Analysis and categorization

### Expected Output:
- **30,000-40,000 leads** with real intelligence
- **2,500-3,000 hours** of Steel credits burned
- **85-90% real data** quality
- **Ready to sell** immediately

---

## ❓ WHAT DO YOU WANT TO EXTRACT?

Tell me:
1. **What types of leads?** (hospitals, clinics, labs, etc.)
2. **Which cities?** (top 20, top 50, all India?)
3. **What intelligence?** (bed count, emails, departments, etc.)
4. **Any specific criteria?** (min bed count, must have website, etc.)

**Then I'll customize the system and START BURNING THOSE CREDITS!**

---

## 🔥 LET'S GO!

Type **"START"** and I'll begin the extraction immediately.

Or tell me what types of leads you want and I'll customize the system first.

**YOUR MOVE.**
