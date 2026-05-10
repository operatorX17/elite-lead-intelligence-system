#!/usr/bin/env python3
"""
Firecrawl MCP Server Testing and Demo Script
Demonstrates how to use Firecrawl MCP tools for ZRAI Lead OS
"""

import json
import sys
from typing import Dict, Any

# This script demonstrates the Firecrawl MCP server tools
# In actual usage via OpenCode, these tools would be invoked automatically

FIRECRAWL_TOOLS = {
    "firecrawl_scrape": {
        "description": "Scrape a single URL and return content",
        "parameters": {
            "url": "string - The URL to scrape",
            "formats": "array - Output formats (markdown, html, etc.)"
        }
    },
    "firecrawl_map": {
        "description": "Map website structure and return all URLs",
        "parameters": {
            "url": "string - Starting URL",
            "sitemap": "boolean - Whether to use sitemap"
        }
    },
    "firecrawl_crawl": {
        "description": "Crawl entire website with specified depth",
        "parameters": {
            "url": "string - Starting URL",
            "maxDepth": "number - Maximum crawl depth",
            "limit": "number - Maximum pages to crawl"
        }
    },
    "firecrawl_search": {
        "description": "Search across multiple websites",
        "parameters": {
            "query": "string - Search query",
            "limit": "number - Maximum results"
        }
    },
    "firecrawl_extract": {
        "description": "Extract structured data using schema",
        "parameters": {
            "url": "string - URL to extract from",
            "schema": "object - JSON schema for extraction"
        }
    },
    "firecrawl_agent": {
        "description": "AI-powered autonomous crawling",
        "parameters": {
            "url": "string - Starting URL",
            "goal": "string - What the AI should accomplish",
            "maxSteps": "number - Maximum steps to take"
        }
    }
}

def print_tool_catalog():
    """Print available Firecrawl MCP tools"""
    print("=" * 80)
    print("Firecrawl MCP Server - Available Tools")
    print("=" * 80)
    print()

    for tool_name, tool_info in FIRECRAWL_TOOLS.items():
        print(f"[TOOL] {tool_name}")
        print(f"   {tool_info['description']}")
        print(f"   Parameters: {tool_info['parameters']}")
        print()

def demo_lead_discovery():
    """Demonstrate Firecrawl usage for ZRAI Lead OS lead discovery"""
    print("\n" + "=" * 80)
    print("Demo: ZRAI Lead OS - Lead Discovery")
    print("=" * 80)
    print()

    # Example: Using firecrawl_extract for business data
    business_schema = {
        "type": "object",
        "properties": {
            "business_name": {"type": "string"},
            "phone": {"type": "string"},
            "email": {"type": "string"},
            "website": {"type": "string"},
            "address": {"type": "string"},
            "services": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["business_name", "phone"]
    }

    print("Example 1: Extract Business Contact Information")
    print("-" * 80)
    print(f"Schema:\n{json.dumps(business_schema, indent=2)}")
    print()
    print("Prompt for OpenCode:")
    print("-" * 80)
    print('Use firecrawl_extract to extract business data from https://example-hvac-company.com')
    print(f'Using schema: {json.dumps(business_schema)}')
    print()

    # Example: Using firecrawl_scrape for page content
    print("Example 2: Scrape Landing Page Content")
    print("-" * 80)
    print("Prompt for OpenCode:")
    print("-" * 80)
    print('Use firecrawl_scrape to scrape https://example-hvac-company.com')
    print('Extract the hero section, service descriptions, and contact information')
    print()

def demo_audit_generation():
    """Demonstrate Firecrawl usage for audit generation"""
    print("\n" + "=" * 80)
    print("Demo: ZRAI Lead OS - Audit Generation")
    print("=" * 80)
    print()

    # Example: Using firecrawl_scrape for audit analysis
    print("Example: Generate Proof Artifacts")
    print("-" * 80)
    print("Prompt for OpenCode:")
    print("-" * 80)
    print('Use firecrawl_scrape to scrape https://example-hvac-company.com')
    print('Analyze:')
    print('1. Phone visibility (is it in the hero section?)')
    print('2. Form field count (contact form complexity)')
    print('3. Booking link presence')
    print('4. Business hours display')
    print('5. Trust signals (reviews, certifications)')
    print('Generate 3 audit bullets with evidence, fix, and upside estimate')
    print()

def demo_niche_research():
    """Demonstrate Firecrawl usage for niche research"""
    print("\n" + "=" * 80)
    print("Demo: ZRAI Lead OS - Niche Research")
    print("=" * 80)
    print()

    print("Example: Research HVAC Contractor Websites")
    print("-" * 80)
    print("Prompt for OpenCode:")
    print("-" * 80)
    print('Use firecrawl_search to find HVAC contractor websites with these patterns:')
    print('- "24/7 emergency service"')
    print('- "Free estimates"')
    print('- "Licensed and insured"')
    print('Limit to 10 results and extract contact information')
    print()

def print_testing_instructions():
    """Print testing instructions"""
    print("\n" + "=" * 80)
    print("Testing Instructions")
    print("=" * 80)
    print()

    print("Step 1: Set up environment variables")
    print("-" * 80)
    print('export FIRECRAWL_API_KEY="fc-your-api-key-here"')
    print()

    print("Step 2: Test MCP server connection")
    print("-" * 80)
    print("opencode mcp debug firecrawl")
    print()

    print("Step 3: Test Firecrawl tools")
    print("-" * 80)
    print("In OpenCode, use prompts like:")
    print('- "Use firecrawl to scrape https://example.com"')
    print('- "Use firecrawl_extract to get business data from https://example.com"')
    print()

    print("Step 4: Verify tool output")
    print("-" * 80)
    print("Check that:")
    print("- Connection is successful")
    print("- API key is valid")
    print("- Tools return expected data")
    print("- No rate limit errors")
    print()

def main():
    """Main function"""
    print("[FIRECRAWL] Firecrawl MCP Server - Testing & Demo for ZRAI Lead OS")
    print()

    # Print tool catalog
    print_tool_catalog()

    # Run demos
    demo_lead_discovery()
    demo_audit_generation()
    demo_niche_research()

    # Print testing instructions
    print_testing_instructions()

    print("\n" + "=" * 80)
    print("Ready to use Firecrawl MCP!")
    print("=" * 80)
    print("\n[INFO] Next steps:")
    print("1. Set FIRECRAWL_API_KEY environment variable")
    print("2. Run: opencode mcp debug firecrawl")
    print("3. Start OpenCode and use prompts above")
    print()

    # Print tool catalog
    print_tool_catalog()

    # Run demos
    demo_lead_discovery()
    demo_audit_generation()
    demo_niche_research()

    # Print testing instructions
    print_testing_instructions()

    print("\n" + "=" * 80)
    print("Ready to use Firecrawl MCP!")
    print("=" * 80)
    print("\n[INFO] Next steps:")
    print("1. Set FIRECRAWL_API_KEY environment variable")
    print("2. Run: opencode mcp debug firecrawl")
    print("3. Start OpenCode and use prompts above")
    print()

if __name__ == "__main__":
    main()
