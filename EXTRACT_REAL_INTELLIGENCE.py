#!/usr/bin/env python3
"""
REAL INTELLIGENCE EXTRACTION - NO MOCKS
Max out signals. Get EVERYTHING.
Uses: Firecrawl, Brave Search, direct scraping
"""

import os
import json
import re
from datetime import datetime
from typing import Dict, Any, List

# Firecrawl for web scraping
try:
    from firecrawl import FirecrawlApp
    FIRECRAWL_AVAILABLE = True
except:
    FIRECRAWL_AVAILABLE = False

# Brave Search
import requests


def brave_search(query: str, count: int = 10) -> List[Dict]:
    """Search using Brave API."""
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        print("⚠️  No BRAVE_API_KEY found")
        return []
    
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key
    }
    params = {
        "q": query,
        "count": count
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("web", {}).get("results", [])
    except Exception as e:
        print(f"Brave Search error: {e}")
        return []


def firecrawl_scrape(url: str) -> Dict[str, Any]:
    """Scrape URL using Firecrawl."""
    if not FIRECRAWL_AVAILABLE:
        print("⚠️  Firecrawl not available")
        return {}
    
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        print("⚠️  No FIRECRAWL_API_KEY found")
        return {}
    
    try:
        app = FirecrawlApp(api_key=api_key)
        result = app.scrape_url(url, params={
            'formats': ['markdown', 'html'],
            'onlyMainContent': True
        })
        return result
    except Exception as e:
        print(f"Firecrawl error: {e}")
        return {}


def extract_google_maps_data(business_name: str, location: str) -> Dict[str, Any]:
    """
    Extract ALL Google Maps data for a business.
    Uses Brave Search to find the business, then scrapes everything.
    """
    
    print(f"\n{'='*100}")
    print(f"EXTRACTING REAL DATA: {business_name}")
    print(f"{'='*100}")
    
    data = {
        "business_name": business_name,
        "location": location,
        "timestamp": datetime.utcnow().isoformat(),
        "sources": [],
        "signals": {}
    }
    
    # Step 1: Find Google Maps listing
    print(f"\n[1/5] Searching for Google Maps listing...")
    
    search_queries = [
        f"{business_name} {location} Google Maps",
        f"{business_name} {location} reviews",
        f"{business_name} {location} rating",
    ]
    
    all_results = []
    for query in search_queries:
        print(f"  → Searching: {query}")
        results = brave_search(query, count=5)
        all_results.extend(results)
        
        # Look for Google Maps URL
        for result in results:
            url = result.get("url", "")
            if "google.com/maps" in url or "goo.gl/maps" in url:
                print(f"  ✓ Found Google Maps: {url}")
                data["sources"].append({
                    "type": "google_maps",
                    "url": url,
                    "title": result.get("title", "")
                })
    
    # Step 2: Find review aggregator sites
    print(f"\n[2/5] Finding review data from aggregators...")
    
    review_sites = ["justdial", "practo", "sulekha", "google", "mouthshut"]
    
    for result in all_results:
        url = result.get("url", "").lower()
        title = result.get("title", "")
        description = result.get("description", "")
        
        for site in review_sites:
            if site in url:
                print(f"  ✓ Found {site}: {result.get('url')}")
                
                # Extract review count from description
                review_match = re.search(r'(\d+[\d,]*)\s*(reviews?|ratings?)', description, re.IGNORECASE)
                if review_match:
                    review_count = int(review_match.group(1).replace(',', ''))
                    print(f"    → {review_count} reviews found")
                    
                    if site not in data["signals"]:
                        data["signals"][site] = {}
                    data["signals"][site]["review_count"] = review_count
                
                # Extract rating
                rating_match = re.search(r'(\d+\.?\d*)\s*/\s*5|rated\s+(\d+\.?\d*)', description, re.IGNORECASE)
                if rating_match:
                    rating = float(rating_match.group(1) or rating_match.group(2))
                    print(f"    → {rating}/5 rating")
                    
                    if site not in data["signals"]:
                        data["signals"][site] = {}
                    data["signals"][site]["rating"] = rating
                
                data["sources"].append({
                    "type": site,
                    "url": result.get("url"),
                    "title": title,
                    "description": description
                })
    
    # Step 3: Scrape business website
    print(f"\n[3/5] Finding and scraping business website...")
    
    website_url = None
    for result in all_results:
        url = result.get("url", "")
        # Skip review sites, look for actual business website
        if not any(site in url.lower() for site in ["google.com", "justdial", "practo", "sulekha", "mouthshut", "facebook", "instagram"]):
            if business_name.lower().replace(" ", "") in url.lower().replace("-", "").replace("_", ""):
                website_url = url
                print(f"  ✓ Found website: {website_url}")
                break
    
    if website_url:
        print(f"  → Scraping website...")
        website_data = firecrawl_scrape(website_url)
        
        if website_data:
            content = website_data.get("markdown", "")
            
            # Extract signals from website
            data["signals"]["website"] = {
                "url": website_url,
                "has_booking": bool(re.search(r'book|appointment|schedule', content, re.IGNORECASE)),
                "has_chat": bool(re.search(r'chat|whatsapp|messenger', content, re.IGNORECASE)),
                "has_forms": len(re.findall(r'<form|contact.*form', content, re.IGNORECASE)),
                "phone_visible": bool(re.search(r'\+?\d{10,}|\(\d{3}\)', content)),
                "email_visible": bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)),
            }
            
            print(f"    ✓ Booking system: {data['signals']['website']['has_booking']}")
            print(f"    ✓ Chat widget: {data['signals']['website']['has_chat']}")
            print(f"    ✓ Forms: {data['signals']['website']['has_forms']}")
    
    # Step 4: Search for pain points in reviews
    print(f"\n[4/5] Searching for pain point evidence...")
    
    pain_queries = [
        f"{business_name} {location} complaints",
        f"{business_name} {location} negative reviews",
        f"{business_name} {location} problems",
    ]
    
    pain_keywords = {
        "missed_calls": ["no response", "didn't call back", "never called", "no reply"],
        "booking_issues": ["hard to book", "couldn't book", "booking problem"],
        "delays": ["long wait", "delayed", "slow service"],
        "communication": ["poor communication", "unresponsive"],
    }
    
    pain_evidence = {key: [] for key in pain_keywords.keys()}
    
    for query in pain_queries:
        results = brave_search(query, count=3)
        
        for result in results:
            description = result.get("description", "").lower()
            
            for pain_type, keywords in pain_keywords.items():
                for keyword in keywords:
                    if keyword in description:
                        pain_evidence[pain_type].append({
                            "source": result.get("url"),
                            "snippet": description[:200],
                            "keyword": keyword
                        })
                        print(f"  🚨 Found '{keyword}' in {result.get('url')}")
    
    data["signals"]["pain_evidence"] = pain_evidence
    
    # Step 5: Aggregate and calculate scores
    print(f"\n[5/5] Calculating intelligence scores...")
    
    # Volume score
    total_reviews = 0
    avg_rating = 0
    rating_count = 0
    
    for site, site_data in data["signals"].items():
        if isinstance(site_data, dict):
            if "review_count" in site_data:
                total_reviews += site_data["review_count"]
            if "rating" in site_data:
                avg_rating += site_data["rating"]
                rating_count += 1
    
    if rating_count > 0:
        avg_rating = avg_rating / rating_count
    
    volume_score = 0
    if total_reviews > 5000:
        volume_score = 100
    elif total_reviews > 1000:
        volume_score = 80
    elif total_reviews > 500:
        volume_score = 60
    elif total_reviews > 100:
        volume_score = 40
    elif total_reviews > 50:
        volume_score = 20
    
    data["intelligence"] = {
        "total_reviews": total_reviews,
        "avg_rating": round(avg_rating, 2),
        "volume_score": volume_score,
        "volume_level": "VERY HIGH" if volume_score >= 80 else ("HIGH" if volume_score >= 60 else ("MEDIUM" if volume_score >= 40 else "LOW")),
    }
    
    # Problem score
    problem_count = 0
    if "website" in data["signals"]:
        ws = data["signals"]["website"]
        if not ws.get("has_booking"):
            problem_count += 1
        if not ws.get("has_chat"):
            problem_count += 1
        if ws.get("has_forms", 0) == 0:
            problem_count += 1
    
    pain_mentions = sum(len(v) for v in pain_evidence.values())
    
    data["intelligence"]["problem_count"] = problem_count
    data["intelligence"]["pain_mentions"] = pain_mentions
    data["intelligence"]["problem_score"] = min(problem_count * 30 + pain_mentions * 2, 100)
    
    # Final score
    final_score = int((volume_score * 0.4) + (data["intelligence"]["problem_score"] * 0.6))
    
    if final_score >= 80:
        tier = "S (ELITE)"
    elif final_score >= 70:
        tier = "A (HOT)"
    elif final_score >= 50:
        tier = "B (WARM)"
    else:
        tier = "C (COLD)"
    
    data["intelligence"]["final_score"] = final_score
    data["intelligence"]["tier"] = tier
    
    print(f"\n{'='*100}")
    print(f"INTELLIGENCE SUMMARY")
    print(f"{'='*100}")
    print(f"Total Reviews: {total_reviews}")
    print(f"Avg Rating: {avg_rating:.1f}/5.0")
    print(f"Volume Score: {volume_score}/100 ({data['intelligence']['volume_level']})")
    print(f"Problems Found: {problem_count}")
    print(f"Pain Mentions: {pain_mentions}")
    print(f"Problem Score: {data['intelligence']['problem_score']}/100")
    print(f"\nFINAL SCORE: {final_score}/100")
    print(f"TIER: {tier}")
    print(f"{'='*100}")
    
    return data


def main():
    """Extract real intelligence for 5 Hyderabad hospitals."""
    
    # Load the 5 REAL hospital targets
    with open("ELITE_INTELLIGENCE_Hyderabad_5_hospitals.json", "r") as f:
        hospitals = json.load(f)
    
    print(f"\n🔥 REAL INTELLIGENCE EXTRACTION - NO MOCKS 🔥")
    print(f"Targets: {len(hospitals)} Hyderabad hospitals")
    print(f"Using: Brave Search + Firecrawl")
    
    all_results = []
    
    for idx, hospital_data in enumerate(hospitals, 1):
        hospital = hospital_data.get("hospital", {})
        business_name = hospital.get("business_name", "")
        location = hospital.get("location", "Hyderabad")
        
        print(f"\n{'#'*100}")
        print(f"HOSPITAL {idx}/{len(hospitals)}")
        print(f"{'#'*100}")
        
        # Extract all data
        data = extract_google_maps_data(business_name, location)
        
        # Add original hospital data
        data["original_data"] = hospital_data
        
        all_results.append(data)
        
        # Save individual result
        safe_name = re.sub(r'[^\w\s-]', '', business_name).replace(' ', '_')[:50]
        filename = f"REAL_INTELLIGENCE_{safe_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        
        print(f"\n✅ Saved: {filename}")
    
    # Save combined results
    combined_filename = f"REAL_INTELLIGENCE_ALL_5_HOSPITALS_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(combined_filename, "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n{'='*100}")
    print(f"✅ ALL HOSPITALS PROCESSED")
    print(f"{'='*100}")
    print(f"Combined results: {combined_filename}")
    print(f"Total hospitals: {len(all_results)}")
    
    # Summary
    print(f"\n{'='*100}")
    print(f"INTELLIGENCE SUMMARY")
    print(f"{'='*100}")
    
    for idx, result in enumerate(all_results, 1):
        intel = result.get("intelligence", {})
        print(f"\n{idx}. {result['business_name']}")
        print(f"   Reviews: {intel.get('total_reviews', 0)}")
        print(f"   Rating: {intel.get('avg_rating', 0):.1f}/5.0")
        print(f"   Volume Score: {intel.get('volume_score', 0)}/100")
        print(f"   Final Score: {intel.get('final_score', 0)}/100")
        print(f"   Tier: {intel.get('tier', 'UNKNOWN')}")
    
    return all_results


if __name__ == "__main__":
    main()
