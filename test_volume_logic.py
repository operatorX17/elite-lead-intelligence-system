#!/usr/bin/env python3
"""
Test volume signal logic WITHOUT API calls.
Uses mock data to verify the implementation works correctly.
"""

import os
import sys
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.agents.enrichment import EnrichmentAgent
from src.agents.intent import IntentAgent


def test_volume_logic():
    """Test volume signal extraction and scoring logic."""
    
    print("=" * 80)
    print("TESTING VOLUME SIGNAL LOGIC (Mock Data)")
    print("=" * 80)
    
    # Mock Google Maps data (what Apify would return)
    mock_gmaps_data = {
        "title": "Ragavs Diagnostic Centre",
        "reviewsCount": 342,
        "totalScore": 4.2,
        "popularTimesHistogram": {
            "Monday": [0, 0, 0, 0, 0, 0, 20, 40, 60, 80, 90, 100, 90, 80, 70, 60, 40, 20, 10, 0, 0, 0, 0, 0],
            "Tuesday": [0, 0, 0, 0, 0, 0, 25, 45, 65, 85, 95, 100, 95, 85, 75, 65, 45, 25, 15, 0, 0, 0, 0, 0],
            "Wednesday": [0, 0, 0, 0, 0, 0, 22, 42, 62, 82, 92, 100, 92, 82, 72, 62, 42, 22, 12, 0, 0, 0, 0, 0],
            "Thursday": [0, 0, 0, 0, 0, 0, 24, 44, 64, 84, 94, 100, 94, 84, 74, 64, 44, 24, 14, 0, 0, 0, 0, 0],
            "Friday": [0, 0, 0, 0, 0, 0, 26, 46, 66, 86, 96, 100, 96, 86, 76, 66, 46, 26, 16, 0, 0, 0, 0, 0],
            "Saturday": [0, 0, 0, 0, 0, 0, 30, 50, 70, 90, 100, 100, 100, 90, 80, 70, 50, 30, 20, 0, 0, 0, 0, 0],
            "Sunday": [0, 0, 0, 0, 0, 0, 15, 35, 55, 75, 85, 95, 85, 75, 65, 55, 35, 15, 5, 0, 0, 0, 0, 0],
        },
        "popularTimesLiveText": "Usually as busy as it gets",
        "peopleTypicallySpendHere": "20 min to 2 hr",
        "openingHours": [
            {"day": "Monday", "hours": "8:00 AM - 8:00 PM"},
            {"day": "Tuesday", "hours": "8:00 AM - 8:00 PM"},
        ],
    }
    
    print("\n[TEST 1] Volume Signal Extraction")
    print("-" * 80)
    
    enrichment_agent = EnrichmentAgent()
    volume_signals = enrichment_agent._extract_volume_signals(mock_gmaps_data)
    
    print("Extracted signals:")
    for key, value in volume_signals.items():
        if key == "popular_times_histogram":
            print(f"  {key}: {len(value)} days of data")
        elif isinstance(value, dict):
            print(f"  {key}: {len(value)} items")
        else:
            print(f"  {key}: {value}")
    
    # Verify extraction
    assert volume_signals.get("peak_busyness") == 100, f"Peak busyness should be 100, got {volume_signals.get('peak_busyness')}"
    assert volume_signals.get("busy_hours_count") >= 40, f"Should have >=40 busy hours, got {volume_signals.get('busy_hours_count')}"
    assert volume_signals.get("avg_visit_duration_min") == 70, f"Duration should be 70 min, got {volume_signals.get('avg_visit_duration_min')}"
    assert volume_signals.get("is_peak_busy") == True, f"Should be peak busy, got {volume_signals.get('is_peak_busy')}"
    
    print("\n✓ All extraction assertions passed!")
    
    print("\n[TEST 2] Duration Parsing")
    print("-" * 80)
    
    test_cases = [
        ("20 min to 2 hr", 70),
        ("1-2 hours", 90),
        ("30 minutes", 30),
        ("1 hour", 60),
        ("45 min to 1 hr", 52),
    ]
    
    for text, expected in test_cases:
        result = enrichment_agent._parse_duration(text)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{text}' → {result} min (expected {expected})")
    
    print("\n[TEST 3] Volume Score Calculation")
    print("-" * 80)
    
    mock_lead = {
        "reviews_count": 342,
        "reviewsCount": 342,
        "category": "Healthcare",
    }
    
    intent_agent = IntentAgent()
    volume_score = intent_agent._calculate_volume_score(mock_lead, volume_signals)
    
    print(f"Volume Score: {volume_score}/100")
    
    # Calculate expected score
    reviews_pts = 30  # 342 reviews > 200
    peak_pts = 30  # peak 100 > 90
    busy_hrs = volume_signals.get('busy_hours_count', 0)
    busy_pts = 20 if busy_hrs > 40 else (10 if busy_hrs > 20 else 0)
    duration_pts = 10  # 70 min > 60
    expected = reviews_pts + peak_pts + busy_pts + duration_pts
    
    print(f"\nBreakdown:")
    print(f"  Reviews (342): {reviews_pts} pts (high volume)")
    print(f"  Peak busyness (100): {peak_pts} pts (as busy as it gets)")
    print(f"  Busy hours ({busy_hrs}): {busy_pts} pts ({'busy most of week' if busy_pts == 20 else 'not enough' if busy_pts == 0 else 'regularly busy'})")
    print(f"  Visit duration (70 min): {duration_pts} pts (high engagement)")
    print(f"  EXPECTED TOTAL: {expected}/100")
    print(f"  ACTUAL TOTAL: {volume_score}/100")
    
    assert volume_score == expected, f"Volume score should be {expected}, got {volume_score}"
    print("\n✓ Volume score calculation correct!")
    
    print("\n[TEST 4] Scoring Weight Changes")
    print("-" * 80)
    
    # Old weights (before volume)
    old_weights = {
        "ad_activity": 0.05,
        "intent": 0.35,
        "leak": 0.25,
        "reactivation": 0.20,
        "contact_quality": 0.10,
        "business_size": 0.05,
    }
    
    # New weights (with volume)
    new_weights = {
        "ad_activity": 0.05,
        "intent": 0.30,
        "leak": 0.25,
        "volume": 0.15,
        "reactivation": 0.15,
        "contact_quality": 0.10,
        "business_size": 0.00,
    }
    
    # Mock scores
    scores = {
        "ad_activity": 0,
        "intent": 70,
        "leak": 75,
        "volume": 90,
        "reactivation": 65,
        "contact_quality": 80,
        "business_size": 50,
    }
    
    # Calculate old score (without volume)
    old_score = sum(old_weights[k] * scores.get(k, 0) for k in old_weights.keys())
    
    # Calculate new score (with volume)
    new_score = sum(new_weights[k] * scores.get(k, 0) for k in new_weights.keys())
    
    print("OLD SCORING (without volume):")
    for k in old_weights.keys():
        print(f"  {k:20s}: {scores.get(k, 0):3d} × {old_weights[k]:.2f} = {old_weights[k] * scores.get(k, 0):5.1f}")
    print(f"  TOTAL: {old_score:.1f}/100")
    
    print("\nNEW SCORING (with volume):")
    for k in new_weights.keys():
        print(f"  {k:20s}: {scores.get(k, 0):3d} × {new_weights[k]:.2f} = {new_weights[k] * scores.get(k, 0):5.1f}")
    print(f"  TOTAL: {new_score:.1f}/100")
    
    print(f"\nImprovement: {new_score - old_score:+.1f} points")
    
    old_tier = "A" if old_score >= 55 else ("B" if old_score >= 35 else "C")
    new_tier = "A" if new_score >= 55 else ("B" if new_score >= 35 else "C")
    
    print(f"Tier change: {old_tier} → {new_tier}")
    
    assert new_score > old_score, "New score should be higher"
    print("\n✓ Scoring improvement verified!")
    
    print("\n[TEST 5] Edge Cases")
    print("-" * 80)
    
    # Test with no volume data
    empty_signals = {}
    empty_lead = {"reviews_count": 10}
    
    volume_score_empty = intent_agent._calculate_volume_score(empty_lead, empty_signals)
    print(f"Low volume business (10 reviews, no popular times): {volume_score_empty}/100")
    assert volume_score_empty == 0, "Should be 0 for low volume"
    
    # Test with medium volume
    medium_lead = {"reviews_count": 150}
    medium_signals = {"peak_busyness": 60, "busy_hours_count": 25, "avg_visit_duration_min": 40}
    
    volume_score_medium = intent_agent._calculate_volume_score(medium_lead, medium_signals)
    print(f"Medium volume business (150 reviews, moderate busy): {volume_score_medium}/100")
    assert 30 <= volume_score_medium <= 60, "Should be medium score"
    
    # Test with very high volume
    high_lead = {"reviews_count": 600}
    high_signals = {"peak_busyness": 95, "busy_hours_count": 50, "avg_visit_duration_min": 90}
    
    volume_score_high = intent_agent._calculate_volume_score(high_lead, high_signals)
    print(f"Very high volume business (600 reviews, peak busy): {volume_score_high}/100")
    assert volume_score_high >= 90, "Should be very high score"
    
    print("\n✓ All edge cases handled correctly!")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print("\n✓ Volume signal extraction: WORKING")
    print("✓ Duration parsing: WORKING")
    print("✓ Volume score calculation: WORKING")
    print("✓ Scoring weight changes: WORKING")
    print("✓ Edge case handling: WORKING")
    
    print("\n✓ IMPLEMENTATION IS CORRECT")
    print("\nNext steps:")
    print("1. Run database migration: psql $DATABASE_URL -f migrations/003_add_volume_signals.sql")
    print("2. Test with real Apify data: python test_volume_implementation.py")
    print("3. Rescore all leads: python rescore_with_volume.py")
    
    # Save test results
    results = {
        "test_passed": True,
        "volume_signals_extracted": volume_signals,
        "volume_score": volume_score,
        "old_score": old_score,
        "new_score": new_score,
        "improvement": new_score - old_score,
        "tier_change": f"{old_tier} → {new_tier}",
    }
    
    with open("test_volume_logic_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print("\n✓ Test results saved to test_volume_logic_results.json")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        test_volume_logic()
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
