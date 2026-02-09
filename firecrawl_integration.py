"""
ZRAI Lead OS - Firecrawl MCP Integration Module
Provides practical examples of using Firecrawl MCP tools for lead discovery, enrichment, and audit
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json


class FirecrawlIntegrator:
    """Integrates Firecrawl MCP tools with ZRAI Lead OS pipeline"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.business_schema = {
            "type": "object",
            "properties": {
                "business_name": {"type": "string"},
                "phone": {"type": "string"},
                "email": {"type": "string"},
                "website": {"type": "string"},
                "address": {"type": "string"},
                "services": {"type": "array", "items": {"type": "string"}},
                "business_hours": {"type": "string"},
                "service_area": {"type": "string"}
            },
            "required": ["business_name", "phone"]
        }

    def extract_business_data(self, url: str) -> Dict[str, Any]:
        """
        Use firecrawl_extract to get structured business data

        Args:
            url: Website URL to scrape

        Returns:
            Dictionary with extracted business information

        Example usage in OpenCode:
            "Use firecrawl_extract to extract business data from {url}"
        """
        print(f"[Firecrawl] Extracting business data from {url}")

        # This would be called via OpenCode MCP tool
        # Returns structured data matching business_schema
        extracted_data = {
            "business_name": "Example HVAC Company",
            "phone": "+1-555-123-4567",
            "email": "contact@exmplehvac.com",
            "website": url,
            "address": "123 Main Street, City, ST 12345",
            "services": ["Heating", "Cooling", "Maintenance"],
            "business_hours": "Mon-Fri 8am-6pm, Sat 9am-2pm",
            "service_area": "Greater Metro Area",
            "extracted_at": datetime.now().isoformat()
        }

        return extracted_data

    def generate_audit_proof(self, url: str) -> Dict[str, Any]:
        """
        Use firecrawl_scrape to generate audit proof artifacts

        Args:
            url: Website URL to audit

        Returns:
            Dictionary with audit bullets and evidence

        Example usage in OpenCode:
            "Use firecrawl_scrape to scrape {url}
            Analyze phone visibility, form fields, booking link, business hours
            Generate 3 audit bullets with evidence, fix, and upside estimate"
        """
        print(f"[Firecrawl] Generating audit proof for {url}")

        # This would be called via OpenCode MCP tool
        audit_data = {
            "url": url,
            "audit_bullets": [
                {
                    "issue": "Phone number buried in footer, not visible in hero",
                    "evidence": "Hero section has no phone, footer at bottom of page",
                    "fix": "Add phone number to hero section with click-to-call button",
                    "upside_estimate": "+25% conversion rate increase"
                },
                {
                    "issue": "Contact form has 8 fields (too many for mobile)",
                    "evidence": "Form requires: name, email, phone, address, issue, budget, timeline, preferred contact, message",
                    "fix": "Simplify to 4 fields: name, phone, email, message",
                    "upside_estimate": "+40% form completion rate"
                },
                {
                    "issue": "No online booking system found",
                    "evidence": "Only email form available, no scheduling link",
                    "fix": "Integrate Calendly or similar booking tool",
                    "upside_estimate": "+15% booking rate, +50% time saved"
                }
            ],
            "additional_findings": {
                "phone_visibility": "low",
                "form_field_count": 8,
                "booking_link_present": False,
                "business_hours_displayed": True,
                "trust_signals": ["reviews", "certifications"]
            },
            "screenshots": [
                "hero_section.png",
                "contact_form.png",
                "footer_area.png"
            ],
            "generated_at": datetime.now().isoformat()
        }

        return audit_data

    def research_niche_leads(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Use firecrawl_search to find leads in specific niche

        Args:
            query: Search query (e.g., "HVAC contractor 24/7 emergency")
            limit: Maximum number of results

        Returns:
            List of lead URLs with metadata

        Example usage in OpenCode:
            "Use firecrawl_search to find {query}
            Limit to {limit} results and extract basic information"
        """
        print(f"[Firecrawl] Searching for leads: {query}")

        # This would be called via OpenCode MCP tool
        leads = [
            {
                "url": "https://example-hvac-1.com",
                "title": "Emergency HVAC Services",
                "snippet": "24/7 emergency heating and cooling repair",
                "services": ["Heating", "Cooling", "Emergency Repair"],
                "service_area": "Downtown Metro"
            },
            {
                "url": "https://example-hvac-2.com",
                "title": "Residential Heating & Cooling",
                "snippet": "Licensed and insured HVAC contractor",
                "services": ["Installation", "Maintenance"],
                "service_area": "Suburban Area"
            }
        ]

        return leads[:limit]

    def map_website_structure(self, url: str) -> Dict[str, Any]:
        """
        Use firecrawl_map to discover all pages on website

        Args:
            url: Website URL to map

        Returns:
            Dictionary with discovered URLs and structure

        Example usage in OpenCode:
            "Use firecrawl_map to discover all pages on {url}
            Focus on service pages, pricing, and contact forms"
        """
        print(f"[Firecrawl] Mapping website structure: {url}")

        # This would be called via OpenCode MCP tool
        site_map = {
            "url": url,
            "pages": [
                {"url": f"{url}/", "type": "home"},
                {"url": f"{url}/services", "type": "services"},
                {"url": f"{url}/about", "type": "about"},
                {"url": f"{url}/contact", "type": "contact"},
                {"url": f"{url}/pricing", "type": "pricing"},
                {"url": f"{url}/reviews", "type": "trust-signal"},
                {"url": f"{url}/blog", "type": "content"}
            ],
            "total_pages": 7,
            "mapped_at": datetime.now().isoformat()
        }

        return site_map


def demo_lead_enrichment():
    """Demonstrate lead enrichment workflow"""
    print("=" * 80)
    print("ZRAI Lead OS - Lead Enrichment Demo")
    print("=" * 80)
    print()

    # Simulate Apify discovery returning basic lead
    apify_lead = {
        "business_name": "Metro HVAC Services",
        "website": "https://metrtohvac-example.com",
        "source": "apify",
        "discovered_at": datetime.now().isoformat()
    }

    print(f"[Apify] Discovered lead: {apify_lead['business_name']}")
    print(f"          Website: {apify_lead['website']}")
    print()

    # Enrich with Firecrawl
    integrator = FirecrawlIntegrator(api_key="mock-key")
    enriched_data = integrator.extract_business_data(apify_lead['website'])

    print("[Firecrawl] Enriched data:")
    print(json.dumps(enriched_data, indent=2))
    print()

    # Merge data
    complete_lead = {**apify_lead, **enriched_data}
    print("[Complete Lead Profile]:")
    print(json.dumps(complete_lead, indent=2))


def demo_audit_generation():
    """Demonstrate audit generation workflow"""
    print("\n" + "=" * 80)
    print("ZRAI Lead OS - Audit Generation Demo")
    print("=" * 80)
    print()

    lead_url = "https://metrtohvac-example.com"
    integrator = FirecrawlIntegrator(api_key="mock-key")
    audit_proof = integrator.generate_audit_proof(lead_url)

    print("[Audit Proof Generated]:")
    print()

    for i, bullet in enumerate(audit_proof['audit_bullets'], 1):
        print(f"Bullet {i}: {bullet['issue']}")
        print(f"  Evidence: {bullet['evidence']}")
        print(f"  Fix: {bullet['fix']}")
        print(f"  Upside: {bullet['upside_estimate']}")
        print()

    print(f"Additional Findings: {json.dumps(audit_proof['additional_findings'], indent=2)}")
    print(f"Screenshots: {audit_proof['screenshots']}")


def demo_niche_research():
    """Demonstrate niche research workflow"""
    print("\n" + "=" * 80)
    print("ZRAI Lead OS - Niche Research Demo")
    print("=" * 80)
    print()

    queries = [
        "HVAC contractor 24/7 emergency service",
        "residential heating and cooling free estimates",
        "licensed and insured HVAC installation"
    ]

    integrator = FirecrawlIntegrator(api_key="mock-key")

    all_leads = []
    for query in queries:
        print(f"\n[Research] Query: {query}")
        leads = integrator.research_niche_leads(query, limit=3)
        all_leads.extend(leads)
        print(f"Found {len(leads)} leads")

    print(f"\n[Total] Discovered {len(all_leads)} potential leads")
    print("[Sample Leads]:")
    for i, lead in enumerate(all_leads[:3], 1):
        print(f"\n{i}. {lead['title']}")
        print(f"   URL: {lead['url']}")
        print(f"   Services: {', '.join(lead['services'])}")
        print(f"   Area: {lead['service_area']}")


if __name__ == "__main__":
    # Run all demos
    demo_lead_enrichment()
    demo_audit_generation()
    demo_niche_research()

    print("\n" + "=" * 80)
    print("Firecrawl MCP Integration - Demo Complete!")
    print("=" * 80)
    print("\n[Ready] Use these patterns in OpenCode with actual Firecrawl MCP tools")
