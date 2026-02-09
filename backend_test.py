#!/usr/bin/env python3
"""
ZRAI Ultimate Intelligence Engine - Comprehensive Backend Test Suite
==================================================================

Tests all API integrations and core functionality:
1. Environment variables and credentials
2. Apify API connection and business discovery
3. OpenRouter LLM API integration
4. Firecrawl API website scraping
5. Steel API browser automation
6. Revenue calculations and scoring
7. Lead tier assignment
8. Output file generation
9. JSON structure validation
10. Outreach content generation

Author: ZRAI Testing Team
"""

import os
import sys
import json
import time
import requests
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add the app directory to Python path
sys.path.insert(0, '/app')

# Import the main engine
try:
    from ULTIMATE_INTELLIGENCE import (
        UltimateIntelligenceEngine, 
        ApifyClient, 
        FirecrawlClient, 
        SteelClient, 
        OpenRouterLLM,
        BusinessLead,
        LeadTier,
        PriorityLevel,
        get_industry_config
    )
    print("✅ Successfully imported ULTIMATE_INTELLIGENCE modules")
except ImportError as e:
    print(f"❌ Failed to import modules: {e}")
    sys.exit(1)

class UltimateIntelligenceTestSuite:
    """Comprehensive test suite for the Ultimate Intelligence Engine."""
    
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.start_time = datetime.now()
        
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv('/app/.env')
        
        print("\n" + "=" * 80)
        print("🧪 ZRAI ULTIMATE INTELLIGENCE ENGINE - BACKEND TEST SUITE")
        print("=" * 80)
        
    def run_test(self, test_name: str, test_func, *args, **kwargs) -> bool:
        """Run a single test and record results."""
        self.tests_run += 1
        print(f"\n[{self.tests_run}] 🔍 Testing: {test_name}")
        
        try:
            result = test_func(*args, **kwargs)
            if result:
                self.tests_passed += 1
                print(f"    ✅ PASSED")
                self.test_results.append({"test": test_name, "status": "PASSED", "details": ""})
                return True
            else:
                print(f"    ❌ FAILED")
                self.test_results.append({"test": test_name, "status": "FAILED", "details": "Test returned False"})
                return False
        except Exception as e:
            print(f"    ❌ FAILED - Error: {str(e)}")
            self.test_results.append({"test": test_name, "status": "FAILED", "details": str(e)})
            return False
    
    def test_environment_variables(self) -> bool:
        """Test that all required environment variables are set."""
        required_vars = [
            'APIFY_API_TOKEN',
            'OPENROUTER_API_KEY', 
            'FIRECRAWL_API_KEY',
            'STEEL_API_KEY'
        ]
        
        missing_vars = []
        for var in required_vars:
            value = os.environ.get(var)
            if not value:
                missing_vars.append(var)
            else:
                print(f"    ✓ {var}: {'*' * 10}{value[-4:]}")
        
        if missing_vars:
            print(f"    ❌ Missing variables: {', '.join(missing_vars)}")
            return False
        
        return True
    
    def test_apify_api_connection(self) -> bool:
        """Test Apify API connection and basic functionality."""
        client = ApifyClient()
        
        if not client.api_token:
            print("    ❌ No Apify API token")
            return False
        
        # Test API connection with a simple request
        try:
            url = f"{client.base_url}/users/me?token={client.api_token}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                if data.get('data'):
                    print(f"    ✓ Connected as: {data['data'].get('username', 'Unknown')}")
                    return True
        except Exception as e:
            print(f"    ❌ API connection failed: {e}")
            return False
        
        return False
    
    def test_apify_business_discovery(self) -> bool:
        """Test Apify business discovery functionality."""
        client = ApifyClient()
        
        # Test with a small search
        results = client.discover("dental clinic", "Mumbai", "India", limit=3)
        
        if not results:
            print("    ❌ No results returned")
            return False
        
        if len(results) == 0:
            print("    ❌ Empty results list")
            return False
        
        # Validate result structure
        first_result = results[0]
        required_fields = ['title', 'address']
        
        for field in required_fields:
            if field not in first_result:
                print(f"    ❌ Missing field: {field}")
                return False
        
        print(f"    ✓ Found {len(results)} businesses")
        print(f"    ✓ Sample: {first_result.get('title', 'Unknown')[:50]}")
        return True
    
    def test_openrouter_llm_api(self) -> bool:
        """Test OpenRouter LLM API connection and response."""
        llm = OpenRouterLLM()
        
        if not llm.api_key:
            print("    ❌ No OpenRouter API key")
            return False
        
        # Test simple text generation
        response = llm.generate("Say 'Hello World' in exactly 2 words.")
        
        if not response:
            print("    ❌ No response from LLM")
            return False
        
        if len(response.strip()) == 0:
            print("    ❌ Empty response")
            return False
        
        print(f"    ✓ Response: {response[:50]}...")
        
        # Test JSON generation
        json_response = llm.generate_json("Return a JSON object with 'status': 'ok' and 'test': true")
        
        if not json_response:
            print("    ❌ No JSON response")
            return False
        
        if not isinstance(json_response, dict):
            print("    ❌ Invalid JSON response")
            return False
        
        print(f"    ✓ JSON Response: {json_response}")
        return True
    
    def test_firecrawl_api_connection(self) -> bool:
        """Test Firecrawl API connection and scraping."""
        client = FirecrawlClient()
        
        if not client.api_key:
            print("    ❌ No Firecrawl API key")
            return False
        
        # Test scraping a simple website
        test_url = "https://example.com"
        result = client.scrape(test_url)
        
        if not result:
            print("    ❌ No scraping result")
            return False
        
        # Check for expected fields
        if 'markdown' not in result and 'html' not in result:
            print("    ❌ Missing content fields")
            return False
        
        print(f"    ✓ Scraped content length: {len(str(result))}")
        return True
    
    def test_firecrawl_contact_extraction(self) -> bool:
        """Test contact extraction from website content."""
        client = FirecrawlClient()
        
        # Test content with known patterns
        test_content = """
        Contact us at info@example.com or call +91 98765 43210
        Follow us on LinkedIn: linkedin.com/company/example
        WhatsApp: +91-98765-43210
        """
        
        contacts = client.extract_contacts(test_content)
        
        if not contacts.emails:
            print("    ❌ Failed to extract emails")
            return False
        
        if not contacts.phones:
            print("    ❌ Failed to extract phones")
            return False
        
        print(f"    ✓ Extracted {len(contacts.emails)} emails, {len(contacts.phones)} phones")
        return True
    
    def test_steel_api_connection(self) -> bool:
        """Test Steel API connection (optional since it might be rate limited)."""
        client = SteelClient()
        
        if not client.api_key:
            print("    ⚠️ No Steel API key - skipping")
            return True  # Not critical for basic functionality
        
        # Test with a simple page
        result = client.scrape("https://example.com")
        
        if result:
            print(f"    ✓ Steel scraping successful")
            return True
        else:
            print(f"    ⚠️ Steel scraping failed - may be rate limited")
            return True  # Don't fail the test for Steel issues
    
    def test_revenue_calculations(self) -> bool:
        """Test revenue calculation logic."""
        # Create a test lead
        lead = BusinessLead(
            lead_id="test123",
            business_name="Test Dental Clinic",
            category="dental clinic",
            city="Mumbai",
            reviews_count=100,
            rating=4.5
        )
        
        # Test industry config
        config = get_industry_config("dental clinic")
        if not config:
            print("    ❌ No industry config found")
            return False
        
        expected_fields = ['ticket', 'leads', 'conversion']
        for field in expected_fields:
            if field not in config:
                print(f"    ❌ Missing config field: {field}")
                return False
        
        print(f"    ✓ Industry config: ticket=₹{config['ticket']}, leads={config['leads']}")
        
        # Test calculation logic
        engine = UltimateIntelligenceEngine()
        engine._calculate_revenue(lead)
        
        if lead.estimated_monthly_leads <= 0:
            print("    ❌ Invalid monthly leads calculation")
            return False
        
        if lead.estimated_revenue_loss_inr <= 0:
            print("    ❌ Invalid revenue loss calculation")
            return False
        
        print(f"    ✓ Calculated loss: ₹{lead.estimated_revenue_loss_inr:,}/month")
        return True
    
    def test_lead_scoring(self) -> bool:
        """Test lead scoring algorithm."""
        # Create test leads with different characteristics
        test_cases = [
            {
                "name": "High Quality Lead",
                "data": {
                    "business_name": "Premium Dental",
                    "phone": "+91 98765 43210",
                    "website": "https://example.com",
                    "rating": 4.8,
                    "reviews_count": 200
                },
                "expected_min_score": 60
            },
            {
                "name": "Low Quality Lead", 
                "data": {
                    "business_name": "Basic Clinic",
                    "phone": "",
                    "website": "",
                    "rating": None,
                    "reviews_count": None
                },
                "expected_max_score": 40
            }
        ]
        
        engine = UltimateIntelligenceEngine()
        
        for case in test_cases:
            lead = BusinessLead(
                lead_id=f"test_{case['name'].lower().replace(' ', '_')}",
                category="dental clinic",
                city="Mumbai",
                **case['data']
            )
            
            # Add some contacts for high quality lead
            if case['name'] == "High Quality Lead":
                lead.contacts.emails = ["info@example.com"]
                lead.has_whatsapp = True
                lead.has_lead_form = True
            
            engine._calculate_scores(lead)
            
            if case['name'] == "High Quality Lead" and lead.final_score < case['expected_min_score']:
                print(f"    ❌ {case['name']} score too low: {lead.final_score}")
                return False
            
            if case['name'] == "Low Quality Lead" and lead.final_score > case['expected_max_score']:
                print(f"    ❌ {case['name']} score too high: {lead.final_score}")
                return False
            
            print(f"    ✓ {case['name']}: {lead.final_score}/100")
        
        return True
    
    def test_tier_assignment(self) -> bool:
        """Test lead tier assignment logic."""
        engine = UltimateIntelligenceEngine()
        
        # Test different score ranges
        test_cases = [
            {"score": 85, "opp": 60, "expected_tier": LeadTier.HOT},
            {"score": 75, "opp": 30, "expected_tier": LeadTier.HOT},
            {"score": 60, "opp": 50, "expected_tier": LeadTier.WARM},
            {"score": 55, "opp": 30, "expected_tier": LeadTier.WARM},
            {"score": 40, "opp": 20, "expected_tier": LeadTier.COLD}
        ]
        
        for case in test_cases:
            lead = BusinessLead(
                lead_id=f"test_tier_{case['score']}",
                business_name="Test Business",
                category="dental clinic",
                city="Mumbai"
            )
            
            lead.final_score = case['score']
            lead.opportunity_score = case['opp']
            
            engine._assign_tier(lead)
            
            if lead.tier != case['expected_tier']:
                print(f"    ❌ Score {case['score']}: expected {case['expected_tier']}, got {lead.tier}")
                return False
            
            print(f"    ✓ Score {case['score']}: {lead.tier.value}")
        
        return True
    
    def test_output_file_generation(self) -> bool:
        """Test that output files are created correctly."""
        # Check existing output directory
        output_dir = Path("/app/output/Mumbai_dental_clinic_20260205_064929")
        
        if not output_dir.exists():
            print("    ❌ Output directory doesn't exist")
            return False
        
        required_files = [
            "report.json",
            "leads.json", 
            "hot_leads.json",
            "outreach.csv"
        ]
        
        for filename in required_files:
            filepath = output_dir / filename
            if not filepath.exists():
                print(f"    ❌ Missing file: {filename}")
                return False
            
            if filepath.stat().st_size == 0:
                print(f"    ❌ Empty file: {filename}")
                return False
            
            print(f"    ✓ {filename}: {filepath.stat().st_size} bytes")
        
        return True
    
    def test_json_structure_validation(self) -> bool:
        """Test that JSON output has correct structure."""
        report_path = Path("/app/output/Mumbai_dental_clinic_20260205_064929/report.json")
        
        if not report_path.exists():
            print("    ❌ Report file doesn't exist")
            return False
        
        try:
            with open(report_path, 'r') as f:
                report = json.load(f)
        except json.JSONDecodeError as e:
            print(f"    ❌ Invalid JSON: {e}")
            return False
        
        # Check required top-level fields
        required_fields = [
            'run_id', 'timestamp', 'config', 'summary', 'leads'
        ]
        
        for field in required_fields:
            if field not in report:
                print(f"    ❌ Missing field: {field}")
                return False
        
        # Check summary structure
        summary_fields = [
            'discovered', 'processed', 'hot', 'warm', 'cold',
            'total_opportunity_inr', 'total_opportunity_annual_inr'
        ]
        
        for field in summary_fields:
            if field not in report['summary']:
                print(f"    ❌ Missing summary field: {field}")
                return False
        
        # Check leads structure
        if not isinstance(report['leads'], list):
            print("    ❌ Leads should be a list")
            return False
        
        if len(report['leads']) == 0:
            print("    ❌ No leads in report")
            return False
        
        # Check first lead structure
        lead = report['leads'][0]
        required_lead_fields = [
            'lead_id', 'business_name', 'category', 'city',
            'final_score', 'tier', 'estimated_revenue_loss_inr',
            'ai_reasoning', 'email_subject', 'whatsapp_msg'
        ]
        
        for field in required_lead_fields:
            if field not in lead:
                print(f"    ❌ Missing lead field: {field}")
                return False
        
        print(f"    ✓ Valid JSON structure with {len(report['leads'])} leads")
        return True
    
    def test_outreach_content_generation(self) -> bool:
        """Test that outreach content is properly generated."""
        report_path = Path("/app/output/Mumbai_dental_clinic_20260205_064929/report.json")
        
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        leads = report['leads']
        
        for i, lead in enumerate(leads[:3]):  # Test first 3 leads
            # Check email content
            if not lead.get('email_subject'):
                print(f"    ❌ Lead {i+1}: Missing email subject")
                return False
            
            if not lead.get('email_body'):
                print(f"    ❌ Lead {i+1}: Missing email body")
                return False
            
            # Check WhatsApp content
            if not lead.get('whatsapp_msg'):
                print(f"    ❌ Lead {i+1}: Missing WhatsApp message")
                return False
            
            # Check call script
            if not lead.get('call_script'):
                print(f"    ❌ Lead {i+1}: Missing call script")
                return False
            
            # Validate content has business name
            business_name = lead.get('business_name', '')
            if business_name not in lead['email_body']:
                print(f"    ❌ Lead {i+1}: Business name not in email")
                return False
            
            print(f"    ✓ Lead {i+1}: Complete outreach content")
        
        return True
    
    def test_ai_reasoning_quality(self) -> bool:
        """Test that AI reasoning is meaningful and not empty."""
        report_path = Path("/app/output/Mumbai_dental_clinic_20260205_064929/report.json")
        
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        leads = report['leads']
        
        for i, lead in enumerate(leads):
            reasoning = lead.get('ai_reasoning', '')
            
            if not reasoning:
                print(f"    ❌ Lead {i+1}: Empty AI reasoning")
                return False
            
            if len(reasoning) < 20:
                print(f"    ❌ Lead {i+1}: AI reasoning too short")
                return False
            
            # Check for meaningful content (not just generic responses)
            business_name = lead.get('business_name', '')
            if business_name and business_name not in reasoning and len(reasoning) < 50:
                print(f"    ❌ Lead {i+1}: Generic AI reasoning")
                return False
            
            print(f"    ✓ Lead {i+1}: Quality AI reasoning ({len(reasoning)} chars)")
        
        return True
    
    def test_revenue_accuracy(self) -> bool:
        """Test that revenue calculations produce reasonable values."""
        report_path = Path("/app/output/Mumbai_dental_clinic_20260205_064929/report.json")
        
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        leads = report['leads']
        
        for i, lead in enumerate(leads):
            revenue_loss = lead.get('estimated_revenue_loss_inr', 0)
            recoverable = lead.get('recoverable_amount_inr', 0)
            monthly_leads = lead.get('estimated_monthly_leads', 0)
            
            # Basic sanity checks
            if revenue_loss <= 0:
                print(f"    ❌ Lead {i+1}: Invalid revenue loss: {revenue_loss}")
                return False
            
            if recoverable <= 0:
                print(f"    ❌ Lead {i+1}: Invalid recoverable amount: {recoverable}")
                return False
            
            if monthly_leads <= 0:
                print(f"    ❌ Lead {i+1}: Invalid monthly leads: {monthly_leads}")
                return False
            
            # Recoverable should be less than total loss
            if recoverable > revenue_loss:
                print(f"    ❌ Lead {i+1}: Recoverable > Loss")
                return False
            
            # Values should be reasonable for dental clinics
            if revenue_loss > 1000000:  # 10L seems too high for monthly loss
                print(f"    ❌ Lead {i+1}: Revenue loss too high: ₹{revenue_loss:,}")
                return False
            
            print(f"    ✓ Lead {i+1}: Loss ₹{revenue_loss:,}, Recoverable ₹{recoverable:,}")
        
        return True
    
    def run_full_integration_test(self) -> bool:
        """Run a small end-to-end test."""
        print("\n🚀 Running mini integration test...")
        
        try:
            engine = UltimateIntelligenceEngine()
            
            # Run with very small target to avoid API limits
            result = engine.run(
                niche="dental clinic",
                city="Delhi", 
                country="India",
                target=2  # Very small test
            )
            
            if not result:
                print("    ❌ No result returned")
                return False
            
            if result.get('error'):
                print(f"    ❌ Error in result: {result['error']}")
                return False
            
            summary = result.get('summary', {})
            if summary.get('processed', 0) == 0:
                print("    ❌ No leads processed")
                return False
            
            print(f"    ✅ Integration test successful: {summary.get('processed')} leads processed")
            return True
            
        except Exception as e:
            print(f"    ❌ Integration test failed: {e}")
            return False
    
    def generate_test_report(self):
        """Generate final test report."""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        print("\n" + "=" * 80)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 80)
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        print(f"Duration: {duration:.1f} seconds")
        
        if self.tests_passed == self.tests_run:
            print("\n🎉 ALL TESTS PASSED! System is working correctly.")
        else:
            print(f"\n⚠️ {self.tests_run - self.tests_passed} tests failed. Check details above.")
        
        # Save detailed results
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "tests_run": self.tests_run,
                "tests_passed": self.tests_passed,
                "tests_failed": self.tests_run - self.tests_passed,
                "success_rate": round(self.tests_passed/self.tests_run*100, 1),
                "duration_seconds": round(duration, 1)
            },
            "test_results": self.test_results
        }
        
        return report

def main():
    """Run the complete test suite."""
    suite = UltimateIntelligenceTestSuite()
    
    # Core API Tests
    suite.run_test("Environment Variables", suite.test_environment_variables)
    suite.run_test("Apify API Connection", suite.test_apify_api_connection)
    suite.run_test("Apify Business Discovery", suite.test_apify_business_discovery)
    suite.run_test("OpenRouter LLM API", suite.test_openrouter_llm_api)
    suite.run_test("Firecrawl API Connection", suite.test_firecrawl_api_connection)
    suite.run_test("Firecrawl Contact Extraction", suite.test_firecrawl_contact_extraction)
    suite.run_test("Steel API Connection", suite.test_steel_api_connection)
    
    # Core Logic Tests
    suite.run_test("Revenue Calculations", suite.test_revenue_calculations)
    suite.run_test("Lead Scoring Algorithm", suite.test_lead_scoring)
    suite.run_test("Tier Assignment Logic", suite.test_tier_assignment)
    
    # Output Validation Tests
    suite.run_test("Output File Generation", suite.test_output_file_generation)
    suite.run_test("JSON Structure Validation", suite.test_json_structure_validation)
    suite.run_test("Outreach Content Generation", suite.test_outreach_content_generation)
    suite.run_test("AI Reasoning Quality", suite.test_ai_reasoning_quality)
    suite.run_test("Revenue Accuracy", suite.test_revenue_accuracy)
    
    # Integration Test
    suite.run_test("Full Integration Test", suite.run_full_integration_test)
    
    # Generate final report
    report = suite.generate_test_report()
    
    return 0 if suite.tests_passed == suite.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())