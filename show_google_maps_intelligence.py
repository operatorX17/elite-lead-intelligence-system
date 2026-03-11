#!/usr/bin/env python3
"""
Show COMPLETE Google Maps Intelligence
Display ALL data: Reviews (full text), Ratings, Popular Times, Busy Hours, Q&A, Everything
"""

import json
import sys

# Load the latest combined results
with open("GOOGLE_MAPS_ALL_5_HOSPITALS_20260209_193529.json", "r") as f:
    hospitals = json.load(f)

print(f"\n{'='*100}")
print(f"COMPLETE GOOGLE MAPS INTELLIGENCE - ALL 5 HOSPITALS")
print(f"{'='*100}\n")

for idx, hospital in enumerate(hospitals, 1):
    if not hospital.get("found"):
        print(f"\n{idx}. {hospital['business_name']}")
        print(f"   ❌ ERROR: {hospital.get('error', 'Unknown error')}\n")
        continue
    
    gm = hospital.get("google_maps_data", {})
    intel = hospital.get("intelligence", {})
    
    print(f"\n{'#'*100}")
    print(f"HOSPITAL {idx}: {hospital['business_name']}")
    print(f"{'#'*100}\n")
    
    # BASIC INFO
    print(f"📍 LOCATION: {gm.get('address', 'N/A')}")
    print(f"📞 PHONE: {gm.get('phone', 'N/A')}")
    print(f"🌐 WEBSITE: {gm.get('website', 'N/A')}")
    print(f"🔗 GOOGLE MAPS: {gm.get('url', 'N/A')}")
    
    # VOLUME SIGNALS
    print(f"\n{'='*80}")
    print(f"VOLUME SIGNALS")
    print(f"{'='*80}")
    print(f"⭐ RATING: {gm.get('rating', 0)}/5.0")
    print(f"📊 TOTAL REVIEWS: {gm.get('reviews_count', 0):,}")
    print(f"🏆 TOTAL SCORE: {gm.get('total_score', 'N/A')}")
    print(f"📈 VOLUME SCORE: {intel.get('volume_score', 0)}/100 ({intel.get('volume_level', 'UNKNOWN')})")
    
    # REVIEWS DISTRIBUTION
    reviews_dist = gm.get('reviews_distribution', {})
    if reviews_dist:
        print(f"\n📊 REVIEWS DISTRIBUTION:")
        for star in [5, 4, 3, 2, 1]:
            count = reviews_dist.get(f'{star}_star', 0)
            if count > 0:
                print(f"   {'⭐' * star}: {count}")
    
    # OPENING HOURS
    print(f"\n{'='*80}")
    print(f"OPENING HOURS")
    print(f"{'='*80}")
    opening_hours = gm.get('opening_hours', [])
    if opening_hours:
        for hours in opening_hours:
            print(f"   {hours}")
    else:
        print(f"   No opening hours data")
    
    if gm.get('temporarily_closed'):
        print(f"   ⚠️  TEMPORARILY CLOSED")
    if gm.get('permanently_closed'):
        print(f"   ❌ PERMANENTLY CLOSED")
    
    # POPULAR TIMES (BUSY HOURS)
    print(f"\n{'='*80}")
    print(f"POPULAR TIMES (BUSY HOURS)")
    print(f"{'='*80}")
    popular_times = gm.get('popular_times', {})
    if popular_times:
        print(f"   ✅ HAS BUSY HOURS DATA")
        for day, hours in popular_times.items():
            if hours:
                print(f"   {day}: {hours}")
    else:
        print(f"   ❌ NO BUSY HOURS DATA")
    
    # Q&A
    print(f"\n{'='*80}")
    print(f"QUESTIONS & ANSWERS")
    print(f"{'='*80}")
    qa = gm.get('questions_and_answers', [])
    print(f"Total Q&A: {len(qa)}")
    if qa:
        for i, item in enumerate(qa[:5], 1):  # Show first 5
            print(f"\n   Q{i}: {item.get('question', 'N/A')}")
            print(f"   A{i}: {item.get('answer', 'N/A')}")
    
    # REVIEWS (FULL TEXT)
    print(f"\n{'='*80}")
    print(f"REVIEWS (FULL TEXT) - First 20")
    print(f"{'='*80}")
    reviews = gm.get('reviews', [])
    print(f"Total Reviews Available: {len(reviews)}")
    
    if reviews:
        for i, review in enumerate(reviews[:20], 1):
            print(f"\n--- REVIEW {i} ---")
            print(f"⭐ Rating: {review.get('stars', 'N/A')}/5")
            print(f"👤 Author: {review.get('name', 'Anonymous')}")
            print(f"📅 Date: {review.get('publishedAtDate', 'N/A')}")
            
            # Review text
            text = review.get('text') or review.get('reviewText') or review.get('textTranslated') or 'No text'
            print(f"💬 Review: {text[:500]}{'...' if len(text) > 500 else ''}")
            
            # Response from owner
            if review.get('responseFromOwnerText'):
                print(f"💼 Owner Response: {review['responseFromOwnerText'][:200]}...")
    
    # IMAGES
    print(f"\n{'='*80}")
    print(f"IMAGES")
    print(f"{'='*80}")
    images = gm.get('images', [])
    print(f"Total Images: {len(images)}")
    if images:
        print(f"First 5 image URLs:")
        for i, img_url in enumerate(images[:5], 1):
            print(f"   {i}. {img_url}")
    
    # ADDITIONAL INFO
    print(f"\n{'='*80}")
    print(f"ADDITIONAL INFO")
    print(f"{'='*80}")
    print(f"Category: {gm.get('category', 'N/A')}")
    print(f"Price Level: {gm.get('price_level', 'N/A')}")
    print(f"Plus Code: {gm.get('plus_code', 'N/A')}")
    
    # PEOPLE ALSO SEARCH
    people_search = gm.get('people_also_search', [])
    if people_search:
        print(f"\nPeople Also Search:")
        for item in people_search[:5]:
            print(f"   - {item}")
    
    # INTELLIGENCE SUMMARY
    print(f"\n{'='*80}")
    print(f"INTELLIGENCE SUMMARY")
    print(f"{'='*80}")
    print(f"Total Reviews: {intel.get('total_reviews', 0):,}")
    print(f"Avg Rating: {intel.get('avg_rating', 0):.1f}/5.0")
    print(f"Volume Score: {intel.get('volume_score', 0)}/100")
    print(f"Has Busy Hours: {intel.get('has_busy_hours', False)}")
    print(f"Problem Mentions: {intel.get('problem_mentions', 0)}")
    print(f"Problem Score: {intel.get('problem_score', 0)}/100")
    print(f"\n🎯 FINAL SCORE: {intel.get('final_score', 0)}/100")
    print(f"🏆 TIER: {intel.get('tier', 'UNKNOWN')}")

print(f"\n{'='*100}")
print(f"END OF INTELLIGENCE REPORT")
print(f"{'='*100}\n")
