"""
CLI for ZRAI Lead OS.
Requirements: 2 (CLI and Execution Modes)
"""

import click
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
import sys
import json

from src.graph.orchestrator import create_orchestrator, LeadOrchestrator
from src.config import load_config
from src.db.client import get_supabase_client
from src.agents.eval import EvalAgent


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("zrai.cli")


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool):
    """ZRAI Lead OS - Autonomous Lead Intelligence + Outreach Engine"""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to config file")
@click.option("--limit", "-l", type=int, default=None, help="Limit number of leads to process")
@click.option("--niche", "-n", type=str, default=None, help="Filter by niche")
def run_daily(config: Optional[str], limit: Optional[int], niche: Optional[str]):
    """
    Run daily lead processing pipeline.
    Requirements: 2.1
    """
    click.echo("Starting daily run...")
    
    try:
        # Load config
        app_config = load_config(config)
        
        # Get leads to process
        db = get_supabase_client()
        leads = db.get_leads_for_processing(limit=limit, niche=niche)
        
        if not leads:
            click.echo("No leads to process")
            return
        
        click.echo(f"Processing {len(leads)} leads...")
        
        # Create orchestrator
        orchestrator = create_orchestrator()
        
        # Track results
        success_count = 0
        failure_count = 0
        errors = []
        
        with click.progressbar(leads, label="Processing leads") as bar:
            for lead in bar:
                lead_id = UUID(lead["lead_id"])
                try:
                    orchestrator.process_lead(lead_id)
                    success_count += 1
                except Exception as e:
                    failure_count += 1
                    errors.append({
                        "lead_id": str(lead_id),
                        "error": str(e),
                    })
                    logger.error(f"Error processing lead {lead_id}: {e}")
        
        # Output summary
        click.echo("\n" + "=" * 50)
        click.echo("EXECUTION SUMMARY")
        click.echo("=" * 50)
        click.echo(f"Total leads: {len(leads)}")
        click.echo(f"Successes: {success_count}")
        click.echo(f"Failures: {failure_count}")
        
        if errors:
            click.echo("\nErrors:")
            for err in errors[:10]:  # Show first 10 errors
                click.echo(f"  - Lead {err['lead_id']}: {err['error']}")
            if len(errors) > 10:
                click.echo(f"  ... and {len(errors) - 10} more errors")
        
        # Run eval
        eval_agent = EvalAgent()
        metrics = eval_agent.metrics_calculator.calculate_daily_metrics(datetime.utcnow())
        
        click.echo("\nDaily Metrics:")
        click.echo(f"  Reply rate: {metrics.get('reply_rate', 0):.2%}")
        click.echo(f"  Meeting rate: {metrics.get('meeting_rate', 0):.2%}")
        click.echo(f"  Total cost: ${metrics.get('total_cost_usd', 0):.2f}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("run_id")
@click.option("--lead-id", "-l", type=str, default=None, help="Specific lead to replay")
def replay_run(run_id: str, lead_id: Optional[str]):
    """
    Replay a historical run.
    Requirements: 2.2
    """
    click.echo(f"Replaying run {run_id}...")
    
    try:
        db = get_supabase_client()
        orchestrator = create_orchestrator()
        
        if lead_id:
            # Replay single lead
            leads = [{"lead_id": lead_id}]
        else:
            # Get all leads from run
            leads = db.get_leads_from_run(run_id)
        
        if not leads:
            click.echo("No leads found for this run")
            return
        
        click.echo(f"Replaying {len(leads)} leads...")
        
        success_count = 0
        failure_count = 0
        
        with click.progressbar(leads, label="Replaying") as bar:
            for lead in bar:
                try:
                    orchestrator.replay_lead(UUID(lead["lead_id"]), run_id)
                    success_count += 1
                except Exception as e:
                    failure_count += 1
                    logger.error(f"Error replaying lead {lead['lead_id']}: {e}")
        
        click.echo(f"\nReplay complete: {success_count} success, {failure_count} failures")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--since", "-s", type=str, required=True, help="Timestamp (ISO format)")
@click.option("--limit", "-l", type=int, default=None, help="Limit number of leads")
def resume_failed(since: str, limit: Optional[int]):
    """
    Resume failed lead executions.
    Requirements: 2.3
    """
    click.echo(f"Resuming failed leads since {since}...")
    
    try:
        since_dt = datetime.fromisoformat(since)
        
        db = get_supabase_client()
        orchestrator = create_orchestrator()
        
        # Get failed leads
        failed_leads = db.get_failed_leads(since=since_dt, limit=limit)
        
        if not failed_leads:
            click.echo("No failed leads to resume")
            return
        
        click.echo(f"Found {len(failed_leads)} failed leads")
        
        success_count = 0
        failure_count = 0
        
        with click.progressbar(failed_leads, label="Resuming") as bar:
            for lead in bar:
                try:
                    orchestrator.resume_lead(UUID(lead["lead_id"]))
                    success_count += 1
                except Exception as e:
                    failure_count += 1
                    logger.error(f"Error resuming lead {lead['lead_id']}: {e}")
        
        click.echo(f"\nResume complete: {success_count} success, {failure_count} failures")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--limit", "-l", type=int, default=10, help="Number of leads to simulate")
@click.option("--niche", "-n", type=str, default=None, help="Filter by niche")
def dry_run(limit: int, niche: Optional[str]):
    """
    Simulate execution without external writes.
    Requirements: 2.4
    """
    click.echo(f"Starting dry run with {limit} leads...")
    
    try:
        db = get_supabase_client()
        orchestrator = create_orchestrator()
        
        # Get leads
        leads = db.get_leads_for_processing(limit=limit, niche=niche)
        
        if not leads:
            click.echo("No leads to process")
            return
        
        click.echo(f"Simulating {len(leads)} leads...")
        
        results = []
        
        with click.progressbar(leads, label="Dry run") as bar:
            for lead in bar:
                try:
                    result = orchestrator.dry_run(UUID(lead["lead_id"]))
                    results.append({
                        "lead_id": str(lead["lead_id"]),
                        "final_stage": result.current_stage,
                        "tier": result.scoring.lead_tier if result.scoring else None,
                        "score": result.scoring.final_score if result.scoring else None,
                    })
                except Exception as e:
                    results.append({
                        "lead_id": str(lead["lead_id"]),
                        "error": str(e),
                    })
        
        # Output results
        click.echo("\n" + "=" * 50)
        click.echo("DRY RUN RESULTS")
        click.echo("=" * 50)
        
        for r in results:
            if "error" in r:
                click.echo(f"  {r['lead_id']}: ERROR - {r['error']}")
            else:
                click.echo(f"  {r['lead_id']}: {r['final_stage']} (Tier {r['tier']}, Score {r['score']})")
        
        click.echo("\nNote: No external writes were performed")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
def status():
    """Show system status and metrics."""
    click.echo("ZRAI Lead OS Status")
    click.echo("=" * 50)
    
    try:
        config = load_config()
        db = get_supabase_client()
        
        # Kill switches
        click.echo("\nKill Switches:")
        click.echo(f"  Global: {'ACTIVE' if config.kill_switches.global_kill else 'inactive'}")
        click.echo(f"  Discovery: {'ACTIVE' if config.kill_switches.discovery_kill else 'inactive'}")
        click.echo(f"  Audit: {'ACTIVE' if config.kill_switches.audit_kill else 'inactive'}")
        click.echo(f"  Outreach: {'ACTIVE' if config.kill_switches.outreach_kill else 'inactive'}")
        
        # Circuit breakers
        click.echo("\nCircuit Breakers:")
        for node in ["discovery", "enrichment", "audit", "outreach"]:
            cb = db.get_circuit_breaker(node)
            if cb:
                click.echo(f"  {node}: {cb.get('state', 'CLOSED')} (failures: {cb.get('failure_count', 0)})")
            else:
                click.echo(f"  {node}: CLOSED")
        
        # Today's usage
        today = datetime.utcnow()
        metrics = db.get_or_create_usage_metrics(today)
        
        click.echo("\nToday's Usage:")
        click.echo(f"  LLM tokens: {metrics.get('llm_tokens_used', 0):,} / {config.budget.daily_llm_token_limit:,}")
        click.echo(f"  Browser sessions: {metrics.get('browser_sessions_used', 0)} / {config.budget.daily_browser_session_limit}")
        click.echo(f"  Scraper runs: {metrics.get('scraper_runs_used', 0)} / {config.budget.daily_scraper_run_limit}")
        
        # Lead counts
        lead_counts = db.get_lead_counts_by_state()
        click.echo("\nLead Counts by State:")
        for state, count in lead_counts.items():
            click.echo(f"  {state}: {count}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--test-name", "-t", type=str, required=True, help="A/B test name")
def ab_status(test_name: str):
    """Show A/B test status and results."""
    click.echo(f"A/B Test: {test_name}")
    click.echo("=" * 50)
    
    try:
        eval_agent = EvalAgent()
        result = eval_agent.ab_framework.evaluate_test(test_name)
        
        click.echo(f"\nVariant A (Control) Metrics:")
        for metric, value in result.variant_a_metrics.items():
            click.echo(f"  {metric}: {value:.4f}")
        
        click.echo(f"\nVariant B (Treatment) Metrics:")
        for metric, value in result.variant_b_metrics.items():
            click.echo(f"  {metric}: {value:.4f}")
        
        click.echo(f"\nWinner: {result.winner or 'TBD'}")
        
        if result.should_rollback:
            click.echo(f"⚠️  ROLLBACK RECOMMENDED: {result.rollback_reason}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("lead_id")
def inspect(lead_id: str):
    """Inspect a specific lead's state and history."""
    click.echo(f"Inspecting lead {lead_id}")
    click.echo("=" * 50)
    
    try:
        db = get_supabase_client()
        
        # Get lead
        lead = db.get_lead(UUID(lead_id))
        if not lead:
            click.echo("Lead not found")
            return
        
        click.echo("\nLead Data:")
        click.echo(f"  Business: {lead.get('business_name')}")
        click.echo(f"  Category: {lead.get('category')}")
        click.echo(f"  Location: {lead.get('location')}")
        click.echo(f"  Lifecycle: {lead.get('lead_lifecycle_state')}")
        click.echo(f"  Last contacted: {lead.get('last_contacted_at')}")
        
        # Get state
        state = db.get_lead_state(UUID(lead_id))
        if state:
            click.echo("\nProcessing State:")
            click.echo(f"  Stage: {state.get('current_stage')}")
            click.echo(f"  Last node: {state.get('last_node')}")
            click.echo(f"  Retry count: {state.get('retry_count')}")
            click.echo(f"  Last error: {state.get('last_error')}")
        
        # Get scoring
        scoring = db.get_scoring_result(UUID(lead_id))
        if scoring:
            click.echo("\nScoring:")
            click.echo(f"  Final score: {scoring.get('final_score')}")
            click.echo(f"  Tier: {scoring.get('lead_tier')}")
            click.echo(f"  DNC: {scoring.get('do_not_contact')}")
            if scoring.get('do_not_contact_reason'):
                click.echo(f"  DNC reason: {scoring.get('do_not_contact_reason')}")
        
        # Get negative signals
        signals = db.get_negative_signals(UUID(lead_id))
        if signals:
            click.echo("\nNegative Signals:")
            for s in signals:
                click.echo(f"  - {s.get('signal_type')} on {s.get('created_at')}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def main():
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
