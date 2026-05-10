#!/usr/bin/env python
"""
Test MiniMax M2.1 Integration
Verify that the MiniMax API is working correctly
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from dotenv import load_dotenv
load_dotenv()

from src.tools.llm import get_llm_client
from rich.console import Console
from rich.panel import Panel

console = Console()


def test_minimax_basic():
    """Test basic text generation"""
    console.print("\n[bold cyan]TEST 1: Basic Text Generation[/bold cyan]")
    
    try:
        llm = get_llm_client()
        
        prompt = "What is the capital of India? Answer in one sentence."
        
        console.print(f"[yellow]Prompt:[/yellow] {prompt}")
        console.print("[yellow]Generating response...[/yellow]")
        
        response = llm.generate(prompt, temperature=0.3, max_tokens=100)
        
        console.print(Panel(response, title="MiniMax M2.1 Response", border_style="green"))
        
        return True
        
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        return False


def test_minimax_reasoning():
    """Test AI reasoning for lead validation"""
    console.print("\n[bold cyan]TEST 2: AI Reasoning (Lead Validation)[/bold cyan]")
    
    try:
        llm = get_llm_client()
        
        prompt = """
You are validating a lead for a healthcare business.

Lead Data:
- Business: Redcliffe Labs (Diagnostic Center)
- Website: https://redcliffelabs.com/
- Phone: +91 89889 88787
- Email: care@redcliffelabs.com
- Has booking system: Yes
- Has WhatsApp: No
- Reviews: Unknown

Task: Analyze this lead and determine if it's a HIGH-QUALITY opportunity.

Provide your analysis in 2-3 sentences.
"""
        
        console.print("[yellow]Generating AI reasoning...[/yellow]")
        
        response = llm.generate(
            prompt,
            system_prompt="You are a Supreme AI Reasoning Agent that validates lead quality.",
            temperature=0.1,
            max_tokens=300
        )
        
        console.print(Panel(response, title="AI Reasoning Analysis", border_style="green"))
        
        return True
        
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        return False


def test_minimax_structured():
    """Test structured JSON output"""
    console.print("\n[bold cyan]TEST 3: Structured JSON Output[/bold cyan]")
    
    try:
        llm = get_llm_client()
        
        prompt = "Analyze this business: Redcliffe Labs, a diagnostic center in Bangalore with a website and email."
        
        schema = {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["HOT", "WARM", "COLD"]},
                "confidence": {"type": "number"},
                "reasoning": {"type": "string"},
                "key_strengths": {"type": "array", "items": {"type": "string"}},
                "opportunities": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["verdict", "confidence", "reasoning"]
        }
        
        console.print("[yellow]Generating structured JSON...[/yellow]")
        
        response = llm.generate_structured(
            prompt,
            schema=schema,
            system_prompt="You are a lead scoring AI. Analyze businesses and provide structured assessments."
        )
        
        import json
        console.print(Panel(
            json.dumps(response, indent=2),
            title="Structured JSON Response",
            border_style="green"
        ))
        
        return True
        
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        return False


def test_minimax_outreach():
    """Test outreach message generation"""
    console.print("\n[bold cyan]TEST 4: Outreach Message Generation[/bold cyan]")
    
    try:
        llm = get_llm_client()
        
        prompt = """
Generate a professional outreach email for this lead:

Business: Redcliffe Labs (Diagnostic Center)
Location: Bangalore
Revenue Loss: ₹180k/month (missed appointments)
Recoverable: ₹125k/month
Recommended Tier: Pro ₹60K/month
ROI: 2.1x

Write a compelling email subject and body (max 150 words).
"""
        
        console.print("[yellow]Generating outreach message...[/yellow]")
        
        response = llm.generate(
            prompt,
            system_prompt="You are an expert B2B sales copywriter specializing in healthcare automation.",
            temperature=0.7,
            max_tokens=500
        )
        
        console.print(Panel(response, title="Outreach Message", border_style="green"))
        
        return True
        
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        return False


def main():
    """Run all tests"""
    console.print(Panel.fit(
        "[bold red]MiniMax M2.1 Integration Test[/bold red]\n\n"
        "[yellow]Testing Elite AI Model for ZRAI Lead OS[/yellow]",
        border_style="red"
    ))
    
    # Check API key
    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        console.print("[red]❌ MINIMAX_API_KEY not found in .env[/red]")
        return
    
    console.print(f"[green]✓ API Key found: {api_key[:20]}...[/green]")
    
    # Run tests
    results = []
    
    results.append(("Basic Generation", test_minimax_basic()))
    results.append(("AI Reasoning", test_minimax_reasoning()))
    results.append(("Structured JSON", test_minimax_structured()))
    results.append(("Outreach Generation", test_minimax_outreach()))
    
    # Summary
    console.print("\n" + "="*60)
    console.print("[bold cyan]TEST SUMMARY[/bold cyan]")
    console.print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[green]✓ PASS[/green]" if result else "[red]❌ FAIL[/red]"
        console.print(f"{status} - {test_name}")
    
    console.print("="*60)
    console.print(f"[bold]Results: {passed}/{total} tests passed[/bold]")
    
    if passed == total:
        console.print("\n[bold green]🎉 All tests passed! MiniMax M2.1 is ready for production![/bold green]")
    else:
        console.print("\n[bold red]⚠️ Some tests failed. Check the errors above.[/bold red]")


if __name__ == "__main__":
    main()
