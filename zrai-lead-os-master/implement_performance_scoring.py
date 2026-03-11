"""
PHASE 2 - TIER 1 - Website Performance Scoring Implementation

This script demonstrates how to add website performance scoring to the enrichment agent.

Usage:
    python implement_performance_scoring.py <website_url>

Example:
    python implement_performance_scoring.py https://example.com
"""

import sys
import time
import requests
from typing import Dict, Any, Optional
from datetime import datetime


def check_website_performance(url: str) -> Dict[str, Any]:
    """
    Check website performance metrics.
    
    Returns:
        {
            "load_time_ms": int,
            "status_code": int,
            "is_https": bool,
            "has_ssl": bool,
            "performance_score": int (0-100),
            "performance_grade": str (A-F),
            "issues": List[str],
        }
    """
    result = {
        "url": url,
        "load_time_ms": 0,
        "status_code": 0,
        "is_https": False,
        "has_ssl": False,
        "performance_score": 0,
        "performance_grade": "F",
        "issues": [],
        "checked_at": datetime.utcnow().isoformat(),
    }
    
    # Ensure URL has protocol
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    
    result["is_https"] = url.startswith("https://")
    
    try:
        # Measure load time
        start_time = time.time()
        response = requests.get(url, timeout=10, allow_redirects=True)
        load_time = (time.time() - start_time) * 1000  # Convert to ms
        
        result["load_time_ms"] = int(load_time)
        result["status_code"] = response.status_code
        
        # Check SSL
        if response.url.startswith("https://"):
            result["has_ssl"] = True
        
        # Calculate performance score
        score = 100
        
        # Load time penalties
        if load_time > 5000:  # >5s
            score -= 40
            result["issues"].append(f"Very slow load time: {int(load_time)}ms (should be <2000ms)")
        elif load_time > 3000:  # >3s
            score -= 25
            result["issues"].append(f"Slow load time: {int(load_time)}ms (should be <2000ms)")
        elif load_time > 2000:  # >2s
            score -= 10
            result["issues"].append(f"Moderate load time: {int(load_time)}ms (optimal: <2000ms)")
        
        # SSL penalties
        if not result["has_ssl"]:
            score -= 20
            result["issues"].append("No SSL certificate (HTTP only)")
        
        # Status code penalties
        if response.status_code >= 400:
            score -= 30
            result["issues"].append(f"HTTP error: {response.status_code}")
        elif response.status_code >= 300:
            score -= 10
            result["issues"].append(f"Redirect: {response.status_code}")
        
        result["performance_score"] = max(0, score)
        
        # Assign grade
        if score >= 90:
            result["performance_grade"] = "A"
        elif score >= 80:
            result["performance_grade"] = "B"
        elif score >= 70:
            result["performance_grade"] = "C"
        elif score >= 60:
            result["performance_grade"] = "D"
        else:
            result["performance_grade"] = "F"
        
    except requests.exceptions.Timeout:
        result["issues"].append("Request timeout (>10s)")
        result["performance_score"] = 0
        result["performance_grade"] = "F"
    except requests.exceptions.SSLError:
        result["issues"].append("SSL certificate error")
        result["performance_score"] = 20
        result["performance_grade"] = "F"
    except requests.exceptions.ConnectionError:
        result["issues"].append("Connection failed")
        result["performance_score"] = 0
        result["performance_grade"] = "F"
    except Exception as e:
        result["issues"].append(f"Error: {str(e)}")
        result["performance_score"] = 0
        result["performance_grade"] = "F"
    
    return result


def calculate_leak_score_impact(performance: Dict[str, Any]) -> int:
    """
    Calculate how much to add to leak_score based on performance issues.
    
    Poor performance = lost leads = revenue leak.
    """
    leak_impact = 0
    
    # Load time impact
    load_time = performance.get("load_time_ms", 0)
    if load_time > 5000:
        leak_impact += 30  # Critical - losing 50%+ of visitors
    elif load_time > 3000:
        leak_impact += 20  # High - losing 30-40% of visitors
    elif load_time > 2000:
        leak_impact += 10  # Moderate - losing 10-20% of visitors
    
    # SSL impact
    if not performance.get("has_ssl"):
        leak_impact += 15  # Trust issues = lost conversions
    
    # Error impact
    if performance.get("status_code", 0) >= 400:
        leak_impact += 25  # Site broken = 100% leak
    
    return min(leak_impact, 50)  # Cap at 50 points


def main():
    if len(sys.argv) < 2:
        print("Usage: python implement_performance_scoring.py <website_url>")
        print("\nExample:")
        print("  python implement_performance_scoring.py https://example.com")
        sys.exit(1)
    
    url = sys.argv[1]
    
    print("=" * 70)
    print("  WEBSITE PERFORMANCE SCORING TEST")
    print("=" * 70)
    print(f"\nTesting: {url}\n")
    
    # Check performance
    performance = check_website_performance(url)
    
    # Display results
    print("PERFORMANCE METRICS:")
    print(f"  Load Time: {performance['load_time_ms']}ms")
    print(f"  Status Code: {performance['status_code']}")
    print(f"  HTTPS: {'✓' if performance['is_https'] else '✗'}")
    print(f"  SSL Certificate: {'✓' if performance['has_ssl'] else '✗'}")
    print(f"\nPERFORMANCE SCORE: {performance['performance_score']}/100 (Grade: {performance['performance_grade']})")
    
    if performance['issues']:
        print(f"\nISSUES FOUND ({len(performance['issues'])}):")
        for i, issue in enumerate(performance['issues'], 1):
            print(f"  {i}. {issue}")
    else:
        print("\n✓ No performance issues found!")
    
    # Calculate leak impact
    leak_impact = calculate_leak_score_impact(performance)
    print(f"\nREVENUE LEAK IMPACT: +{leak_impact} points")
    
    if leak_impact > 0:
        print("\nRECOMMENDATIONS:")
        if performance['load_time_ms'] > 3000:
            print("  • Optimize images and assets")
            print("  • Enable caching")
            print("  • Use a CDN")
        if not performance['has_ssl']:
            print("  • Install SSL certificate (free with Let's Encrypt)")
        if performance['status_code'] >= 400:
            print("  • Fix broken pages")
    
    print("\n" + "=" * 70)
    print("  INTEGRATION GUIDE")
    print("=" * 70)
    print("""
To integrate this into the enrichment agent:

1. Add to src/agents/enrichment.py:
   
   from implement_performance_scoring import check_website_performance, calculate_leak_score_impact
   
   # In EnrichmentAgent.process():
   if website:
       performance = check_website_performance(website)
       enrichment["performance_metrics"] = performance
       
       # Update leak score in intent agent
       leak_impact = calculate_leak_score_impact(performance)
       # Store for use in intent scoring

2. Add to src/db/models.py:
   
   class EnrichmentData(BaseModel):
       ...
       performance_metrics: Optional[Dict[str, Any]] = None

3. Add migration:
   
   ALTER TABLE enrichment_data 
   ADD COLUMN performance_metrics JSONB;

4. Update src/agents/intent.py to use performance data:
   
   # In _compute_leak_score():
   performance = enrichment.get("performance_metrics", {})
   if performance:
       leak_impact = calculate_leak_score_impact(performance)
       score += leak_impact
""")


if __name__ == "__main__":
    main()

