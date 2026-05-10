# WHAT'S ACTUALLY BROKEN - THE BRUTAL TRUTH

## YOUR ORIGINAL GOAL (From Day 1)

**Insurance Claim Recovery System for Hospitals:**
- Find hospitals losing ₹87.5 lakhs/month in rejected insurance claims
- Offer AI system to validate claims BEFORE submission
- Reduce rejection rate from 35% to <10%
- Charge ₹35,000/month for 175x ROI (₹61.2L/month recovery)
- First customer in 2 weeks

## WHAT THE SYSTEM SHOULD DO

### 1. Discovery Agent ✅ WORKING
- Scrape Google Maps for hospitals
- Get: name, location, phone, website, reviews, rating
- **STATUS:** 100% working via Apify

### 2. Enrichment Agent ❌ BROKEN
**SHOULD DO:**
- Use **FIRECRAWL** to scrape hospital websites
- Detect tech signals:
  - ❌ Broken booking systems
  - ❌ No WhatsApp integration  
  - ❌ Missing lead forms
  - ❌ No chat widgets
  - ❌ Call-only CTAs (revenue leak!)
  - ❌ No online payment
  - ❌ Slow website (>3s load)

**ACTUALLY DOES:**
- Uses Apify's basic crawler (NOT Firecrawl!)
- Doesn't properly detect booking systems
- Doesn't find WhatsApp links
- Doesn't analyze forms
- Doesn't check chat widgets
- **RESULT:** Enrichment data is mostly empty/wrong

### 3. Intent Agent ⚠️ PARTIALLY WORKING
- Calculates volume score (working with review count)
- Calculates intent score (working)
- Calculates leak score (BROKEN - needs real enrichment data)
- **STATUS:** Works but with bad input data

### 4. Scoring Agent ✅ WORKING
- Weighted scoring formula works
- Tier classification works
- **STATUS:** Works but garbage in = garbage out

### 5. Audit Agent ❌ NOT IMPLEMENTED
**SHOULD DO:**
- Use **STEEL.DEV** browser automation
- Navigate to hospital website
- Take screenshots of:
  - Hero section
  - Booking form (or lack of it)
  - Contact page
  - WhatsApp button (or lack of it)
- Generate "proof artifacts" showing revenue leaks
- **STATUS:** Not implemented at all!

### 6. Outreach Agent ❌ NOT IMPLEMENTED
**SHOULD DO:**
- Generate personalized emails with proof screenshots
- Show exact ₹ amount being lost
- Offer free audit
- **STATUS:** Not implemented at all!

## WHAT'S MISSING

### 1. Firecrawl Integration ❌
**File:** `src/tools/firecrawl_enrichment.py`
**Problem:** Uses Apify crawler instead of Firecrawl MCP
**Impact:** Can't detect booking systems, WhatsApp, forms, chat widgets

**FIX NEEDED:**
```python
# Current (BROKEN):
crawl_result = self._apify.crawl_website(website, max_pages=5)

# Should be (WORKING):
result = await mcp_firecrawl_scrape({
    "url": website,
    "formats": [{"type": "json", "schema": booking_schema}]
})
```

### 2. Steel.dev Browser Automation ❌
**File:** `src/agents/audit.py` (DOESN'T EXIST!)
**Problem:** Audit agent not implemented
**Impact:** No proof artifacts, no screenshots, no visual evidence

**FIX NEEDED:**
- Create `src/agents/audit.py`
- Use Steel MCP to navigate websites
- Take screenshots
- Generate audit bullets with evidence

### 3. Outreach Message Generation ❌
**File:** `src/agents/outreach.py` (EXISTS BUT INCOMPLETE)
**Problem:** Doesn't use proof artifacts
**Impact:** Generic messages, no personalization, low conversion

**FIX NEEDED:**
- Update outreach agent to include screenshots
- Add exact ₹ calculations
- Include proof of revenue leaks

## CURRENT PIPELINE STATUS

```
Discovery (Apify) ✅
    ↓
Enrichment (Apify crawler - BROKEN) ❌
    ↓
Intent (Works but bad data) ⚠️
    ↓
Scoring (Works but garbage in) ⚠️
    ↓
Audit (NOT IMPLEMENTED) ❌
    ↓
Outreach (INCOMPLETE) ❌
```

## WHAT YOU'RE GETTING NOW

**For HK Hospitals (74 reviews, 4.3 rating):**
- ✅ Business name: HK Hospitals
- ✅ Location: Hyderabad
- ✅ Phone: +91 90523 39052
- ✅ Website: https://hkhospitals.in/
- ✅ Reviews: 74
- ✅ Rating: 4.3
- ❌ Booking system: Unknown (should be detected)
- ❌ WhatsApp: Unknown (should be detected)
- ❌ Chat widget: Unknown (should be detected)
- ❌ Lead form: Unknown (should be detected)
- ❌ Screenshots: None (audit agent missing)
- ❌ Proof artifacts: None (audit agent missing)

**Scoring:**
- Volume: 10/100 (based on 74 reviews - WORKING)
- Intent: 100/100 (has website, phone, good rating - WORKING)
- Leak: 50/100 (GUESSED - should be based on real signals)
- Final: 64/100, Tier A

## WHAT YOU SHOULD BE GETTING

**For HK Hospitals:**
- ✅ All basic info (name, location, phone, website, reviews, rating)
- ✅ Booking system: DETECTED (Calendly/Acuity/None)
- ✅ WhatsApp: DETECTED (has wa.me link or not)
- ✅ Chat widget: DETECTED (Intercom/Drift/None)
- ✅ Lead form: DETECTED (has form or not)
- ✅ Form friction: DETECTED (5+ fields = high friction)
- ✅ Website speed: DETECTED (>3s = slow)
- ✅ Screenshots: 3 images (hero, booking, contact)
- ✅ Audit bullets: 3 specific issues with ₹ impact
- ✅ Outreach message: Personalized with proof

**Scoring:**
- Volume: 10/100 (based on 74 reviews)
- Intent: 100/100 (has website, phone, good rating)
- Leak: 80/100 (NO booking system, NO WhatsApp, NO chat widget)
- Final: 72/100, Tier A (higher score due to real leak detection)

## THE FIX

### Priority 1: Fix Enrichment Agent (Use Firecrawl)
**Time:** 2 hours
**Impact:** HIGH - enables real tech signal detection

**Steps:**
1. Update `src/agents/enrichment.py` to use Firecrawl MCP
2. Add proper schema for booking system detection
3. Add WhatsApp link detection
4. Add chat widget detection
5. Add form analysis
6. Test with HK Hospitals website

### Priority 2: Implement Audit Agent (Use Steel)
**Time:** 4 hours
**Impact:** HIGH - enables proof artifacts

**Steps:**
1. Create `src/agents/audit.py`
2. Use Steel MCP for browser automation
3. Navigate to website
4. Take 3 screenshots (hero, booking, contact)
5. Generate audit bullets with ₹ impact
6. Store screenshots in object storage
7. Test with HK Hospitals

### Priority 3: Update Outreach Agent
**Time:** 2 hours
**Impact:** MEDIUM - improves conversion

**Steps:**
1. Update `src/agents/outreach.py`
2. Include proof screenshots in message
3. Add exact ₹ calculations
4. Add specific revenue leak examples
5. Test message generation

### Priority 4: Build Dashboard
**Time:** 4 hours
**Impact:** MEDIUM - enables validation

**Steps:**
1. Create Next.js dashboard
2. Connect to Supabase
3. Show leads with screenshots
4. Show audit bullets
5. Show outreach messages
6. Enable manual review/approval

## BOTTOM LINE

**What works:** Discovery, basic scoring
**What's broken:** Enrichment (using wrong tool), Audit (missing), Outreach (incomplete)
**What you need:** Firecrawl for enrichment, Steel for audit, proper outreach templates

**Time to fix:** 12 hours total
**Impact:** Transform from "basic lead scraper" to "revenue leak detection system"

**Your choice:**
1. Fix enrichment + audit + outreach = Full system working
2. Keep current system = Basic lead scraper with guessed signals

**What do you want to do?**
