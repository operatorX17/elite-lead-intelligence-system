"""
Lead-OS V2 Configuration Module
================================
Industry configs, scoring weights, niche definitions, and default parameters.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


# ─── Enums ─────────────────────────────────────────────────────────────────────

class LeadTier(str, Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"

class PriorityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ─── Industry Configurations ──────────────────────────────────────────────────

INDUSTRY_CONFIG: Dict[str, Dict] = {
    # Healthcare
    "diagnostic":   {"ticket": 1500,   "leads": 500,  "conversion": 0.25, "label": "Diagnostics / Labs"},
    "hospital":     {"ticket": 15000,  "leads": 1000, "conversion": 0.20, "label": "Hospitals"},
    "clinic":       {"ticket": 800,    "leads": 300,  "conversion": 0.30, "label": "Clinics"},
    "dental":       {"ticket": 2500,   "leads": 200,  "conversion": 0.35, "label": "Dental Clinics"},
    "eye":          {"ticket": 3000,   "leads": 150,  "conversion": 0.30, "label": "Eye Care"},
    "derma":        {"ticket": 1500,   "leads": 200,  "conversion": 0.35, "label": "Dermatology"},
    "skin":         {"ticket": 1500,   "leads": 200,  "conversion": 0.35, "label": "Skin / Hair"},
    "physio":       {"ticket": 800,    "leads": 100,  "conversion": 0.40, "label": "Physiotherapy"},
    "ivf":          {"ticket": 150000, "leads": 50,   "conversion": 0.15, "label": "IVF / Fertility"},
    "cosmetic":     {"ticket": 50000,  "leads": 80,   "conversion": 0.20, "label": "Cosmetic Surgery"},
    "vet":          {"ticket": 1500,   "leads": 100,  "conversion": 0.35, "label": "Veterinary"},
    "ayurveda":     {"ticket": 1200,   "leads": 120,  "conversion": 0.30, "label": "Ayurveda / Wellness"},
    "pharmacy":     {"ticket": 500,    "leads": 400,  "conversion": 0.40, "label": "Pharmacy"},
    # Home Services
    "plumber":      {"ticket": 2000,   "leads": 150,  "conversion": 0.40, "label": "Plumbing"},
    "electrician":  {"ticket": 1500,   "leads": 150,  "conversion": 0.40, "label": "Electrical"},
    "hvac":         {"ticket": 5000,   "leads": 80,   "conversion": 0.30, "label": "HVAC"},
    "contractor":   {"ticket": 100000, "leads": 30,   "conversion": 0.15, "label": "Construction"},
    "interior":     {"ticket": 200000, "leads": 20,   "conversion": 0.10, "label": "Interior Design"},
    "pest":         {"ticket": 2500,   "leads": 100,  "conversion": 0.35, "label": "Pest Control"},
    "cleaning":     {"ticket": 3000,   "leads": 80,   "conversion": 0.35, "label": "Cleaning Services"},
    # Professional
    "lawyer":       {"ticket": 10000,  "leads": 50,   "conversion": 0.20, "label": "Legal"},
    "ca":           {"ticket": 5000,   "leads": 80,   "conversion": 0.25, "label": "CA / Accounting"},
    "consultant":   {"ticket": 15000,  "leads": 40,   "conversion": 0.20, "label": "Consulting"},
    # Education
    "coaching":     {"ticket": 50000,  "leads": 100,  "conversion": 0.15, "label": "Coaching"},
    "tuition":      {"ticket": 30000,  "leads": 80,   "conversion": 0.20, "label": "Tuition"},
    "school":       {"ticket": 80000,  "leads": 50,   "conversion": 0.10, "label": "Schools"},
    # Hospitality
    "restaurant":   {"ticket": 800,    "leads": 500,  "conversion": 0.45, "label": "Restaurant"},
    "hotel":        {"ticket": 5000,   "leads": 200,  "conversion": 0.25, "label": "Hotel"},
    "salon":        {"ticket": 1500,   "leads": 200,  "conversion": 0.40, "label": "Salon / Spa"},
    "gym":          {"ticket": 3000,   "leads": 150,  "conversion": 0.25, "label": "Gym / Fitness"},
    # Automotive
    "car_service":  {"ticket": 5000,   "leads": 100,  "conversion": 0.30, "label": "Car Service"},
    "dealer":       {"ticket": 500000, "leads": 30,   "conversion": 0.05, "label": "Auto Dealer"},
    # Real Estate
    "real_estate":  {"ticket": 1000000, "leads": 20,  "conversion": 0.03, "label": "Real Estate"},
    # Default
    "default":      {"ticket": 3000,   "leads": 150,  "conversion": 0.25, "label": "General Business"},
}


def get_industry_config(category: str) -> Dict:
    """Match a category string to the closest industry config."""
    if not category:
        return INDUSTRY_CONFIG["default"]
    cat = category.lower()
    for key, config in INDUSTRY_CONFIG.items():
        if key in cat:
            return config
    return INDUSTRY_CONFIG["default"]


# ─── Niche Search Configurations ─────────────────────────────────────────────

NICHE_KEYWORDS: Dict[str, List[str]] = {
    "dental":          ["dental clinic", "dental hospital", "dentist"],
    "diagnostic":      ["diagnostic centre", "pathology lab", "diagnostic center"],
    "hospital":        ["hospital", "multi-speciality hospital", "medical center"],
    "skin":            ["skin clinic", "dermatology", "hair clinic", "dermatologist"],
    "eye":             ["eye hospital", "ophthalmologist", "eye clinic"],
    "ivf":             ["IVF clinic", "fertility centre", "fertility center"],
    "physio":          ["physiotherapy", "physio clinic", "rehabilitation center"],
    "vet":             ["veterinary clinic", "vet hospital", "animal hospital"],
    "salon":           ["beauty salon", "spa", "hair salon", "unisex salon"],
    "gym":             ["gym", "fitness centre", "crossfit"],
    "restaurant":      ["restaurant", "cafe", "fine dining"],
    "hotel":           ["hotel", "resort", "boutique hotel"],
    "real_estate":     ["real estate agent", "property dealer", "realtor"],
    "coaching":        ["coaching institute", "coaching classes", "test prep"],
    "lawyer":          ["law firm", "advocate", "lawyer"],
    "ca":              ["chartered accountant", "CA firm", "accounting firm"],
    "plumber":         ["plumber", "plumbing services"],
    "electrician":     ["electrician", "electrical contractor"],
    "interior":        ["interior designer", "interior decoration"],
    "contractor":      ["building contractor", "construction company"],
    "car_service":     ["car service center", "auto repair", "car workshop"],
    "mixed":           ["dental clinic", "diagnostic centre", "skin clinic",
                        "eye hospital", "physiotherapy", "polyclinic", "hospital"],
}


# ─── Scoring Weights ─────────────────────────────────────────────────────────

SCORING_WEIGHTS = {
    "data_quality":   0.15,
    "reachability":   0.20,
    "opportunity":    0.30,
    "urgency":        0.15,
    "growth":         0.10,
    "marketing_gap":  0.10,
}

TIER_THRESHOLDS = {
    "hot":  65,   # score >= 65 → HOT
    "warm": 40,   # score >= 40 → WARM
}


# ─── Tracking / Tech Detection Patterns ──────────────────────────────────────

CMS_PATTERNS = {
    "wordpress":   ["wp-content", "wordpress", "wp-json", "wp-includes"],
    "wix":         ["wix.com", "_wix", "wixsite"],
    "shopify":     ["shopify", "cdn.shopify"],
    "squarespace": ["squarespace"],
    "webflow":     ["webflow"],
    "joomla":      ["joomla", "/media/system/"],
    "drupal":      ["drupal", "/sites/default/"],
    "ghost":       ["ghost.org", "/ghost/"],
    "weebly":      ["weebly"],
    "godaddy":     ["godaddy", "secureserver.net"],
}

BOOKING_SYSTEM_PATTERNS = {
    "practo":      ["practo"],
    "zocdoc":      ["zocdoc"],
    "calendly":    ["calendly"],
    "setmore":     ["setmore"],
    "acuity":      ["acuity", "acuityscheduling"],
    "simplybook":  ["simplybook"],
    "appointy":    ["appointy"],
    "booknetic":   ["booknetic"],
    "mindbody":    ["mindbody"],
    "fresha":      ["fresha"],
    "cliniko":     ["cliniko"],
}

CHAT_WIDGET_PATTERNS = {
    "intercom":   ["intercom"],
    "zendesk":    ["zendesk", "zdassets"],
    "freshdesk":  ["freshdesk", "freshchat"],
    "tawk":       ["tawk.to"],
    "crisp":      ["crisp.chat"],
    "drift":      ["drift.com"],
    "livechat":   ["livechatinc", "livechat"],
    "hubspot":    ["hubspot", "hs-scripts"],
    "tidio":      ["tidio"],
    "olark":      ["olark"],
}

ANALYTICS_PATTERNS = ["google-analytics", "gtag", "fbq", "hotjar", "mixpanel",
                       "amplitude", "clarity", "segment", "heap"]

PAYMENT_PATTERNS = ["razorpay", "paytm", "phonepe", "stripe", "paypal",
                     "instamojo", "cashfree"]


# ─── Revenue Tier Thresholds ─────────────────────────────────────────────────

REVENUE_TIERS = [
    {"min_loss": 200000, "tier": "Enterprise ₹1.5L/month", "cost": 150000},
    {"min_loss": 100000, "tier": "Pro ₹60K/month",         "cost": 60000},
    {"min_loss": 50000,  "tier": "Growth ₹35K/month",      "cost": 35000},
    {"min_loss": 0,      "tier": "Starter ₹15K/month",     "cost": 15000},
]


# ─── Cache / Rate Limit Defaults ─────────────────────────────────────────────

CACHE_DIR = ".cache"
CACHE_EXPIRY_HOURS = 48
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds
RATE_LIMIT_DELAY = 1.5  # seconds between API calls
BATCH_SIZE = 5  # leads per parallel batch
