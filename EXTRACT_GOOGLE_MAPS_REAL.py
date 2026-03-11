#!/usr/bin/env python3
"""
EXTRACT REAL GOOGLE MAPS DATA - Using Apify Actor
Get EVERYTHING: Reviews, Ratings, Busy Hours, Popular Times, Q&A, Images
NO MOCKS. REAL DATA ONLY.
"""

import os
import json
import sys
from datetime import datetime, UTC
from typing import Dict, Any, List

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from tools.apify import ApifyClient


def extract_google_maps_intelligence(business_name: str, location: str) -> Dict[str, Any]:
    """
    Extract COMPLETE Google Maps intelligence using Apify actor.
    Gets: Reviews, Ratings, Popular Times, Busy Hours, Q&A, Images, Everything.
    """
    
    print(f"\n{'='*100}")
    print(f"🔥 EXTRACTING GOOGLE MAPS DATA: {business_name}")
    print(f"{'='*100}")
    
    # Initialize Apify client
    apify = ApifyClient()
    
    # Parse location
    location_parts = [p.strip() for p in location.split(',')]
    geo = {
        "city": location_parts[0] if len(location_parts) > 0 else "",
        "state": location_parts[1] if len(location_parts) > 1 else "",
        "country": location_parts[2] if len(location_parts) > 2 else "India"
    }
    
    print(f"\n[1/3] Running Apify Google Maps Actor...")
    print(f"  → Search: {business_name}")
    print(f"  → Location: {geo}")
    print(f"  → Extracting: Reviews, Ratings, Popular Times, Busy Hours, Q&A, Images")
    
    try:
        # Run Google Maps scraper with MAXIMUM signal extraction
        results = apify.run_google_maps_scraper(
            keywords=[business_name],
            geo=geo,
            limit=5  # Get top 5 matches
        )
        
        print(f"  ✓ Found {len(results)} results")
        
        if not results:
            print(f"  ⚠️  No results found for {business_name}")
            return {
                "business_name": business_name,
                "location": location,
                "timestamp": datetime.now(UTC).isoformat(),
                "found": False,
                "error": "No Google Maps results found"
            }
        
        # Take the first result (best match)
        place = results[0]
        
        print(f"\n[2/3] Extracting signals from Google Maps data...")
        
        # Extract ALL signals
        data = {
            "business_name": business_name,
            "location": location,
            "timestamp": datetime.now(UTC).isoformat(),
            "found": True,
            "google_maps_data": {
                "place_id": place.get("placeId"),
                "title": place.get("title"),
                "address": place.get("address"),
                "phone": place.get("phone"),
                "website": place.get("website"),
                "url": place.get("url"),
                
                # VOLUME SIGNALS
                "total_score": place.get("totalScore"),
                "reviews_count": place.get("reviewsCount", 0),
                "rating": place.get("rating", 0.0),
                
                # POPULAR TIMES (Busy hours)
                "popular_times": place.get("popularTimesHistogram", {}),
                
                # OPENING HOURS
                "opening_hours": place.get("openingHours", []),
                "temporarily_closed": place.get("temporarilyClosed", False),
                "permanently_closed": place.get("permanentlyClosed", False),
                
                # Q&A
                "questions_and_answers": place.get("questionsAndAnswers", []),
                "questions_count": len(place.get("questionsAndAnswers", [])),
                
                # IMAGES
                "images": place.get("imageUrls", []),
                "images_count": len(place.get("imageUrls", [])),
                
                # REVIEWS (with sentiment)
                "reviews": place.get("reviews", []),
                "reviews_distribution": place.get("reviewsDistribution", {}),
                
                # ADDITIONAL SIGNALS
                "category": place.get("categoryName"),
                "price_level": place.get("priceLevel"),
                "plus_code": place.get("plusCode"),
                "location_link": place.get("locationLink"),
                
                # PEOPLE ALSO SEARCH
                "people_also_search": place.get("peopleAlsoSearch", []),
                
                # ADDITIONAL INFO
                "additional_info": place.get("additionalInfo", {}),
            }
        }
        
        print(f"  ✓ Reviews: {data['google_maps_data']['reviews_count']:,}")
        print(f"  ✓ Rating: {data['google_maps_data']['rating']:.1f}/5.0")
        print(f"  ✓ Popular Times: {'Yes' if data['google_maps_data']['popular_times'] else 'No'}")
        print(f"  ✓ Opening Hours: {len(data['google_maps_data']['opening_hours'])} entries")
        print(f"  ✓ Q&A: {data['google_maps_data']['questions_count']} questions")
        print(f"  ✓ Images: {data['google_maps_data']['images_count']} images")
        
        print(f"\n[3/3] Calculating intelligence scores...")
        
        # Calculate volume score
        reviews = data['google_maps_data']['reviews_count']
        rating = data['google_maps_data']['rating']
        
        if reviews > 5000:
            volume_score = 100
        elif reviews > 1000:
            volume_score = 80
        elif reviews > 500:
            volume_score = 60
        elif reviews > 100:
            volume_score = 40
        elif reviews > 50:
            volume_score = 20
        else:
            volume_score = 0
        
        # Analyze popular times for busyness
        popular_times = data['google_maps_data']['popular_times']
        has_busy_hours = bool(popular_times)
        
        # Calculate problem score from reviews
        problem_keywords = ['wait', 'delay', 'slow', 'no response', 'missed call', 'hard to book', 'poor service']
        problem_mentions = 0
        
        for review in data['google_maps_data']['reviews'][:20]:  # Check first 20 reviews
            review_text = review.get('text') or review.get('reviewText') or ''
            if review_text:
                review_text = review_text.lower()
                for keyword in problem_keywords:
                    if keyword in review_text:
                        problem_mentions += 1
                        break
        
        problem_score = min(problem_mentions * 5, 100)
        
        # Final score
        final_score = int((volume_score * 0.4) + (problem_score * 0.6))
        
        # Tier
        if final_score >= 80:
            tier = "S (ELITE)"
        elif final_score >= 70:
            tier = "A (HOT)"
        elif final_score >= 50:
            tier = "B (WARM)"
        else:
            tier = "C (COLD)"
        
        data["intelligence"] = {
            "total_reviews": reviews,
            "avg_rating": rating,
            "volume_score": volume_score,
            "volume_level": "VERY HIGH" if volume_score >= 80 else ("HIGH" if volume_score >= 60 else ("MEDIUM" if volume_score >= 40 else "LOW")),
            "has_busy_hours": has_busy_hours,
            "problem_mentions": problem_mentions,
            "problem_score": problem_score,
            "final_score": final_score,
            "tier": tier
        }
        
        print(f"\n{'='*100}")
        print(f"INTELLIGENCE SUMMARY")
        print(f"{'='*100}")
        print(f"Total Reviews: {reviews:,}")
        print(f"Avg Rating: {rating:.1f}/5.0")
        print(f"Volume Score: {volume_score}/100 ({data['intelligence']['volume_level']})")
        print(f"Has Busy Hours: {has_busy_hours}")
        print(f"Problem Mentions: {problem_mentions}")
        print(f"Problem Score: {problem_score}/100")
        print(f"\nFINAL SCORE: {final_score}/100")
        print(f"TIER: {tier}")
        print(f"{'='*100}")
        
        return data
        
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return {
            "business_name": business_name,
            "location": location,
            "timestamp": datetime.now(UTC).isoformat(),
            "found": False,
            "error": str(e)
        }


def main():
    """Extract Google Maps data for 5 Hyderabad hospitals."""
    
    # Load the 5 REAL hospital targets
    with open("ELITE_INTELLIGENCE_Hyderabad_5_hospitals.json", "r") as f:
        hospitals = json.load(f)
    
    print(f"\n🔥 GOOGLE MAPS REAL DATA EXTRACTION 🔥")
    print(f"Targets: {len(hospitals)} Hyderabad hospitals")
    print(f"Using: Apify Google Maps Actor")
    print(f"Extracting: Reviews, Ratings, Popular Times, Busy Hours, Q&A, Images, EVERYTHING")
    
    all_results = []
    
    for idx, hospital_data in enumerate(hospitals, 1):
        hospital = hospital_data.get("hospital", {})
        business_name = hospital.get("business_name", "")
        location = hospital.get("location", "Hyderabad")
        
        print(f"\n{'#'*100}")
        print(f"HOSPITAL {idx}/{len(hospitals)}")
        print(f"{'#'*100}")
        
        # Extract Google Maps data
        data = extract_google_maps_intelligence(business_name, location)
        
        # Add original hospital data
        data["original_data"] = hospital_data
        
        all_results.append(data)
        
        # Save individual result
        safe_name = business_name.replace(' ', '_').replace('|', '').replace('&', 'and')[:50]
        filename = f"GOOGLE_MAPS_{safe_name}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        
        print(f"\n✅ Saved: {filename}")
    
    # Save combined results
    combined_filename = f"GOOGLE_MAPS_ALL_5_HOSPITALS_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(combined_filename, "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n{'='*100}")
    print(f"✅ ALL HOSPITALS PROCESSED")
    print(f"{'='*100}")
    print(f"Combined results: {combined_filename}")
    print(f"Total hospitals: {len(all_results)}")
    
    # Summary
    print(f"\n{'='*100}")
    print(f"GOOGLE MAPS INTELLIGENCE SUMMARY")
    print(f"{'='*100}")
    
    for idx, result in enumerate(all_results, 1):
        if result.get("found"):
            intel = result.get("intelligence", {})
            print(f"\n{idx}. {result['business_name']}")
            print(f"   Reviews: {intel.get('total_reviews', 0):,}")
            print(f"   Rating: {intel.get('avg_rating', 0):.1f}/5.0")
            print(f"   Volume Score: {intel.get('volume_score', 0)}/100")
            print(f"   Final Score: {intel.get('final_score', 0)}/100")
            print(f"   Tier: {intel.get('tier', 'UNKNOWN')}")
        else:
            print(f"\n{idx}. {result['business_name']}")
            print(f"   ❌ NOT FOUND: {result.get('error', 'Unknown error')}")
    
    return all_results


if __name__ == "__main__":
    main()
