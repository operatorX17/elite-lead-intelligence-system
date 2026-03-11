#!/usr/bin/env python3
import json

# Load data
with open('GOOGLE_MAPS_ALL_5_HOSPITALS_20260209_193529.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# St Theresa's (Hospital 4 - has 2,737 reviews!)
hospital = data[3]
gm = hospital['google_maps_data']

print("="*80)
print(f"HOSPITAL: {hospital['business_name']}")
print("="*80)
print(f"Total Reviews: {gm['reviews_count']}")
print(f"Rating: {gm.get('rating', 'N/A')}")
print(f"Address: {gm.get('address', 'N/A')}")
print(f"Phone: {gm.get('phone', 'N/A')}")
print(f"Website: {gm.get('website', 'N/A')}")

print("\n" + "="*80)
print("FIRST 10 REVIEWS (FULL TEXT)")
print("="*80)

reviews = gm.get('reviews', [])
for i, review in enumerate(reviews[:10], 1):
    print(f"\n--- REVIEW {i} ---")
    print(f"Stars: {review.get('stars', 'N/A')}/5")
    print(f"Author: {review.get('name', 'Anonymous')}")
    print(f"Date: {review.get('publishedAtDate', 'N/A')}")
    
    text = review.get('text') or review.get('reviewText') or review.get('textTranslated') or 'No text'
    print(f"Review Text: {text}")
    
    if review.get('responseFromOwnerText'):
        print(f"Owner Response: {review['responseFromOwnerText']}")

print("\n" + "="*80)
print("OPENING HOURS")
print("="*80)
for hours in gm.get('opening_hours', []):
    print(hours)

print("\n" + "="*80)
print("POPULAR TIMES (BUSY HOURS)")
print("="*80)
popular = gm.get('popular_times', {})
if popular:
    for day, times in popular.items():
        print(f"{day}: {times}")
else:
    print("No popular times data available")

print("\n" + "="*80)
print("Q&A")
print("="*80)
qa = gm.get('questions_and_answers', [])
print(f"Total Q&A: {len(qa)}")
for i, item in enumerate(qa[:5], 1):
    print(f"\nQ{i}: {item.get('question', 'N/A')}")
    print(f"A{i}: {item.get('answer', 'N/A')}")
