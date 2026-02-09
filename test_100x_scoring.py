"""
Quick test to verify 100X scoring improvements are working.
"""
import os
from dotenv import load_dotenv
load_dotenv()

from src.agents.intent import IntentAgent, HIGH_TICKET_CATEGORIES
from src.agents.scoring import ScoringAgent

def test_category_matching():
    """Test that category matching works correctly."""
    agent = IntentAgent()
    
    # These should all match
    test_cases = [
        ("Dentist", True),
        ("Dental clinic", True),
        ("Plumber", True),
        ("Plumbing services", True),
        ("Chiropractor", True),
        ("Medical clinic", True),
        ("HVAC contractor", True),
        ("Roofing company", True),
        ("Financial institution", True),
        ("Law firm", True),
        # These should NOT match
        ("Software company", False),
        ("Restaurant", False),
        ("Coffee shop", False),
    ]
    
    print("Testing category matching:")
    print("-" * 50)
    
    all_passed = True
    for category, expected in test_cases:
        result = agent._is_high_ticket_category(category)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"  {status} '{category}' -> {result} (expected {expected})")
    
    print("-" * 50)
    print(f"Category matching: {'PASSED' if all_passed else 'FAILED'}")
    return all_passed


def test_intent_scoring():
    """Test intent scoring with sample lead data."""
    agent = IntentAgent()
    
    # High-ticket lead with good signals
    lead_good = {
        "category": "Dentist",
        "website": "https://example-dental.com",
        "phone": "(555) 123-4567",
        "emails_found": ["info@example.com"],
        "rating": 4.5,
        "review_count": 50,
        "address": "123 Main St",
    }
    
    # Low-signal lead
    lead_poor = {
        "category": "Software company",
        "website": None,
        "phone": None,
        "emails_found": [],
    }
    
    score_good = agent._compute_intent_score(lead_good, {})
    score_poor = agent._compute_intent_score(lead_poor, {})
    
    print("\nTesting intent scoring:")
    print("-" * 50)
    print(f"  High-ticket dentist with good signals: {score_good}")
    print(f"  Low-signal software company: {score_poor}")
    
    passed = score_good > 60 and score_poor < 30
    print(f"Intent scoring: {'PASSED' if passed else 'FAILED'}")
    return passed


def test_tier_assignment():
    """Test tier thresholds."""
    agent = ScoringAgent()
    
    test_scores = [
        (70, "A"),
        (55, "A"),
        (50, "B"),
        (35, "B"),
        (30, "C"),
        (20, "C"),
    ]
    
    print("\nTesting tier assignment:")
    print("-" * 50)
    
    all_passed = True
    for score, expected_tier in test_scores:
        tier = agent._assign_tier(score)
        status = "✓" if tier == expected_tier else "✗"
        if tier != expected_tier:
            all_passed = False
        print(f"  {status} Score {score} -> Tier {tier} (expected {expected_tier})")
    
    print("-" * 50)
    print(f"Tier assignment: {'PASSED' if all_passed else 'FAILED'}")
    return all_passed


def main():
    print("=" * 60)
    print("  ZRAI 100X SCORING VERIFICATION TEST")
    print("=" * 60)
    
    results = []
    results.append(("Category Matching", test_category_matching()))
    results.append(("Intent Scoring", test_intent_scoring()))
    results.append(("Tier Assignment", test_tier_assignment()))
    
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    print(f"  OVERALL: {'ALL TESTS PASSED ✓' if all_passed else 'SOME TESTS FAILED ✗'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
