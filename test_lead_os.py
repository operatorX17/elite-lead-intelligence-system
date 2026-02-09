#!/usr/bin/env python
"""
Test LEAD OS with a small batch
"""

import asyncio
from lead_os import LeadOSPipeline
from rich.console import Console

console = Console()

async def test_small_batch():
    """Test with 10 leads"""
    
    console.print("\n[bold]Testing LEAD OS with 10 Bangalore diagnostics leads...[/bold]\n")
    
    pipeline = LeadOSPipeline(
        city="Bangalore",
        niche="diagnostics",
        target_count=10
    )
    
    await pipeline.run()
    
    console.print("\n[bold green]✅ Test complete![/bold green]")
    console.print(f"Check output/{pipeline.run_id}/ for results")

if __name__ == "__main__":
    asyncio.run(test_small_batch())
