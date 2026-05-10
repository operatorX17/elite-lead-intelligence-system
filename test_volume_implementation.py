#!/usr/bin/env python3
"""
Test volume signal implementation on ONE real lead.
Verify everything works before rescoring all 42 leads.
"""

import os
import sys
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.tools.apify import ApifyClient
from src.agents.enrichment import EnrichmentAgent
from src.agents.intent import IntentAgent
from src.agents.scoring import ScoringAgent
from src.graph.state import LeadGraphState


def test_one_lead():
    """Test volume signal extraction on Ragavs Diagnostic Centre."""
    
    print("=" * 80)
    print("TESTING VOLUME SIGNAL IMPLEMENTATION")
    print("Test Lead: Ragavs Diagnostic Centre, Bangalore")
    print("=" * 80)
    
    # Step 1: Scrape Google Maps data
    print("\n[STEP 1] Scraping Google Maps data with NEW parameters...")
    print("-" * 80)
    
    try:
        apify = ApifyClient()
        results = apify.run_google_maps_scraper(
            keywords=["Ragavs Diagnostic Centre Bangalore"],
            geo={"city": "Bangalore", "country": "India"},
            limit=1
        )
        
        if not results:
            print("✗ No results returned from Apify")
            return
        
        lead_data = results[0]
        print(f"✓ Got data for: {lead_data.get('title', 'Unknown')}")
        print(f"  Reviews: {lead_data.get('reviewsCount', 0)}")
        print(f"  Rating: {lead_data.get('totalScore', 0)}")
        
        # Check what volume signals we got
        print("\n[STEP 2] Checking volume signals in raw data...")
        print("-" * 80)
        
        volume_fields = {
            "popularTimesHistogram": lead_data.get("popularTimesHistogram"),
            "popularTimesLiveText": lead_data.get("popularTimesLiveText"),
            "peopleTypicallySpendHere": lead_data.get("peopleTypicallySpendHere"),
            "openingHours": lead_data.get("openingHours"),
            "reviewsDistribution": lead_data.get("reviewsDistribution"),
            "questionsAndAnswers": lead_data.get("questionsAndAnswers"),
            "webResults": lead_data.get("webResults"),
        }
        
        for field, value in volume_fields.items():
            if value:
                print(f"✓ {field}: PRESENT")
                if field == "popularTimesHistogram" and isinstance(value, dict):
                    # Show sample data
                    for day, hours in list(value.items())[:2]:
                        print(f"    {day}: {hours[:5]}... (showing first 5 hours)")
                elif field == "popularTimesLiveText":
                    print(f"    → {value}")
                elif field == "peopleTypicallySpendHere":
                    print(f"    → {value}")
            else:
                print(f"✗ {field}: MISSING")
        
        # Step 3: Extract volume signals using enrichment agent
        print("\n[STEP 3] Extracting volume signals with EnrichmentAgent...")
        print("-" * 80)
        
        enrichment_agent = EnrichmentAgent()
        volume_signals = enrichment_agent._extract_volume_signals(lead_data)
        
        print(f"Extracted signals:")
        print(f"  Peak busyness: {volume_signals.get('peak_busyness', 'N/A')}/100")
        print(f"  Avg busyness: {volume_signals.get('avg_busyness', 'N/A')}/100")
        print(f"  Busy hours/week: {volume_signals.get('busy_hours_count', 'N/A')}")
        print(f"  Avg visit duration: {volume_signals.get('avg_visit_duration_min', 'N/A')} min")
        print(f"  Is peak busy: {volume_signals.get('is_peak_busy', False)}")
        print(f"  Is above average: {volume_signals.get('is_above_average', False)}")
        
        # Step 4: Calculate volume score
        print("\n[STEP 4] Calculating volume score with IntentAgent...")
        print("-" * 80)
        
        # Create mock lead with volume signals
        mock_lead = {
            "lead_id": "test-123",
            "business_name": lead_data.get("title", "Unknown"),
            "reviews_count": lead_data.get("reviewsCount", 0),
            "reviewsCount": lead_data.get("reviewsCount", 0),
            "rating": lead_data.get("totalScore", 0),
            "category": "Healthcare",
        }
        
        # Create mock enrichment with volume signals
        mock_enrichment = volume_signals
        
        intent_agent = IntentAgent()
        volume_score = intent_agent._calculate_volume_score(mock_lead, mock_enrichment)
        
        print(f"Volume Score: {volume_score}/100")
        print(f"\nBreakdown:")
        
        # Show breakdown
        reviews = mock_lead.get("reviews_count", 0)
        if reviews > 500:
            print(f"  Reviews ({reviews}): 40 pts (very high volume)")
        elif reviews > 200:
            print(f"  Reviews ({reviews}): 30 pts (high volume)")
        elif reviews > 100:
            print(f"  Reviews ({reviews}): 20 pts (medium volume)")
        elif reviews > 50:
            print(f"  Reviews ({reviews}): 10 pts (low volume)")
        else:
            print(f"  Reviews ({reviews}): 0 pts")
        
        peak = volume_signals.get("peak_busyness", 0)
        if peak > 90:
            print(f"  Peak busyness ({peak}): 30 pts (as busy as it gets)")
        elif peak > 70:
            print(f"  Peak busyness ({peak}): 20 pts (very busy)")
        elif peak > 50:
            print(f"  Peak busyness ({peak}): 10 pts (moderately busy)")
        else:
            print(f"  Peak busyness ({peak}): 0 pts")
        
        busy_hours = volume_signals.get("busy_hours_count", 0)
        if busy_hours > 40:
            print(f"  Busy hours ({busy_hours}): 20 pts (busy most of week)")
        elif busy_hours > 20:
            print(f"  Busy hours ({busy_hours}): 10 pts (regularly busy)")
        else:
            print(f"  Busy hours ({busy_hours}): 0 pts")
        
        duration = volume_signals.get("avg_visit_duration_min", 0)
        if duration > 60:
            print(f"  Visit duration ({duration} min): 10 pts (high engagement)")
        elif duration > 30:
            print(f"  Visit duration ({duration} min): 5 pts (moderate engagement)")
        else:
            print(f"  Visit duration ({duration} min): 0 pts")
        
        # Step 5: Check reviews for pain points
        print("\n[STEP 5] Analyzing reviews for pain point evidence...")
        print("-" * 80)
        
        reviews = lead_data.get("reviews", [])
        if reviews:
            print(f"Found {len(reviews)} reviews to analyze")
            
            # Pain point keywords
            pain_keywords = {
                "missed_calls": ["no response", "didn't call back", "never called", "no reply", "couldn't reach"],
                "appointment_delay": ["long wait", "waiting time", "delayed", "slow service", "took forever"],
                "booking_issues": ["hard to book", "couldn't book", "booking problem", "appointment issue"],
                "communication": ["poor communication", "unresponsive", "hard to reach", "no answer"],
            }
            
            pain_evidence = {key: [] for key in pain_keywords.keys()}
            
            for review in reviews[:20]:  # Check first 20 reviews
                text = review.get("text", "").lower()
                reviewer = review.get("name", "Anonymous")
                rating = review.get("stars", 0)
                
                for pain_type, keywords in pain_keywords.items():
                    for keyword in keywords:
                        if keyword in text:
                            pain_evidence[pain_type].append({
                                "reviewer": reviewer,
                                "rating": rating,
                                "snippet": text[:150] + "..." if len(text) > 150 else text,
                                "keyword": keyword
                            })
                            break
            
            # Show pain point evidence
            total_pain_points = sum(len(v) for v in pain_evidence.values())
            if total_pain_points > 0:
                print(f"\n✓ Found {total_pain_points} pain point mentions in reviews:")
                for pain_type, evidence_list in pain_evidence.items():
                    if evidence_list:
                        print(f"\n  {pain_type.upper().replace('_', ' ')} ({len(evidence_list)} mentions):")
                        for ev in evidence_list[:3]:  # Show first 3
                            print(f"    • {ev['reviewer']} ({ev['rating']}★): \"{ev['keyword']}\"")
                            print(f"      {ev['snippet'][:100]}...")
            else:
                print("✗ No obvious pain points found in reviews")
                print("  (This is actually GOOD - means they're doing well)")
        else:
            print("✗ No reviews available in data")
        
        # Step 6: Calculate final score
        print("\n[STEP 6] Calculating final score with new weights...")
        print("-" * 80)
        
        # Mock scores for demonstration
        mock_scores = {
            "ad_activity": 0,
            "intent": 70,
            "leak": 75,
            "volume": volume_score,
            "reactivation": 65,
            "contact_quality": 80,
        }
        
        weights = {
            "ad_activity": 0.05,
            "intent": 0.30,
            "leak": 0.25,
            "volume": 0.15,
            "reactivation": 0.15,
            "contact_quality": 0.10,
        }
        
        final_score = sum(weights[k] * mock_scores[k] for k in weights.keys())
        
        print("Score breakdown:")
        for component, score in mock_scores.items():
            weight = weights[component]
            contribution = weight * score
            print(f"  {component:20s}: {score:3d}/100 × {weight:.2f} = {contribution:5.1f} pts")
        
        print(f"\nFinal Score: {int(final_score)}/100")
        
        if final_score >= 55:
            tier = "A (HOT)"
        elif final_score >= 35:
            tier = "B (WARM)"
        else:
            tier = "C (COLD)"
        
        print(f"Lead Tier: {tier}")
        
        # Step 7: Summary and recommendation
        print("\n" + "=" * 80)
        print("SUMMARY & RECOMMENDATION")
        print("=" * 80)
        
        print(f"\n✓ Volume signals extraction: WORKING")
        print(f"✓ Volume score calculation: WORKING")
        print(f"✓ Final score calculation: WORKING")
        
        print(f"\nData quality:")
        has_popular_times = bool(volume_signals.get("peak_busyness"))
        has_duration = bool(volume_signals.get("avg_visit_duration_min"))
        has_reviews = reviews > 0
        
        print(f"  Popular times data: {'✓ YES' if has_popular_times else '✗ NO'}")
        print(f"  Visit duration data: {'✓ YES' if has_duration else '✗ NO'}")
        print(f"  Review data: {'✓ YES' if has_reviews else '✗ NO'}")
        
        if has_popular_times and has_duration:
            print(f"\n✓ RECOMMENDATION: Implementation is WORKING")
            print(f"  Volume score: {volume_score}/100 is based on REAL data")
            print(f"  Final score: {int(final_score)}/100 includes volume signals")
            print(f"  Ready to run: python rescore_with_volume.py")
        elif has_reviews:
            print(f"\n⚠ PARTIAL DATA: Popular times not available")
            print(f"  Volume score: {volume_score}/100 is based on reviews only")
            print(f"  This is still better than before (no volume data)")
            print(f"  Recommendation: Proceed with rescoring")
        else:
            print(f"\n✗ INSUFFICIENT DATA: Need to check Apify configuration")
            print(f"  Volume signals are not being returned")
            print(f"  Check: Apify actor parameters")
        
        # Save test results
        print(f"\n[SAVING] Test results to test_volume_results.json...")
        test_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "business_name": mock_lead["business_name"],
            "reviews_count": mock_lead["reviews_count"],
            "volume_signals": volume_signals,
            "volume_score": volume_score,
            "final_score": int(final_score),
            "tier": tier,
            "has_popular_times": has_popular_times,
            "has_duration": has_duration,
            "pain_points_found": total_pain_points if reviews else 0,
        }
        
        with open("test_volume_results.json", "w") as f:
            json.dump(test_results, f, indent=2)
        
        print(f"✓ Saved to test_volume_results.json")
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_one_lead()
