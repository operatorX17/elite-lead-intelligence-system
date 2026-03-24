"""
Eval Agent for ZRAI Lead OS.
Requirements: 15 (Evaluation and Offline Replay)
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import logging
import json
import random
from dataclasses import dataclass

from src.graph.state import LeadGraphState
from src.db.client import get_supabase_client
from src.db.models import Lead, ScoringResult, LeadTier
from src.config import load_config


logger = logging.getLogger(__name__)


@dataclass
class GoldenDatasetEntry:
    """
    Golden dataset entry for evaluation.
    Requirements: 15.1
    """
    lead_id: UUID
    input_data: Dict[str, Any]
    expected_score: int
    expected_tier: LeadTier
    expected_outreach_quality: str  # 'good' or 'bad'
    known_outcome: str  # 'replied', 'meeting', 'closed', 'no_response'
    notes: str = ""


@dataclass
class ReplayMetrics:
    """
    Metrics from offline replay comparison.
    Requirements: 15.2
    """
    baseline_version: str
    new_version: str
    score_correlation: float
    tier_agreement: float
    outreach_quality_delta: float
    false_positive_rate_delta: float
    total_leads: int
    score_diffs: List[int]


@dataclass
class ABTestConfig:
    """A/B test configuration."""
    name: str
    variants: List[Dict[str, Any]]
    metrics: List[str]
    guardrails: Dict[str, float]
    sample_size: int
    duration_days: int


@dataclass
class ABTestResult:
    """A/B test results."""
    test_name: str
    variant_a_metrics: Dict[str, float]
    variant_b_metrics: Dict[str, float]
    winner: Optional[str]
    should_rollback: bool
    rollback_reason: Optional[str]


class GoldenDataset:
    """
    Golden dataset manager for evaluation.
    Requirements: 15.1
    """
    
    def __init__(self):
        self._db = get_supabase_client()
        self._logger = logging.getLogger("zrai.eval.golden_dataset")
    
    def load(self) -> List[GoldenDatasetEntry]:
        """
        Load golden dataset from database.
        Requirements: 15.1
        """
        entries = self._db.get_golden_dataset()
        return [
            GoldenDatasetEntry(
                lead_id=UUID(e["lead_id"]),
                input_data=e["input_data"],
                expected_score=e["expected_score"],
                expected_tier=LeadTier(e["expected_tier"]),
                expected_outreach_quality=e["expected_outreach_quality"],
                known_outcome=e["known_outcome"],
                notes=e.get("notes", ""),
            )
            for e in entries
        ]
    
    def add_entry(self, entry: GoldenDatasetEntry) -> None:
        """Add entry to golden dataset."""
        self._db.add_golden_dataset_entry({
            "lead_id": str(entry.lead_id),
            "input_data": entry.input_data,
            "expected_score": entry.expected_score,
            "expected_tier": entry.expected_tier.value,
            "expected_outreach_quality": entry.expected_outreach_quality,
            "known_outcome": entry.known_outcome,
            "notes": entry.notes,
        })
    
    def get_by_outcome(self, outcome: str) -> List[GoldenDatasetEntry]:
        """Get entries by known outcome."""
        all_entries = self.load()
        return [e for e in all_entries if e.known_outcome == outcome]


class OfflineReplay:
    """
    Offline replay system for evaluation.
    Requirements: 15.2
    """
    
    def __init__(self):
        self._db = get_supabase_client()
        self._config = load_config()
        self._golden_dataset = GoldenDataset()
        self._logger = logging.getLogger("zrai.eval.replay")
    
    def run_replay(
        self,
        scoring_func,
        version: str,
        baseline_version: str,
    ) -> ReplayMetrics:
        """
        Run offline replay and compare to baseline.
        Requirements: 15.2
        """
        dataset = self._golden_dataset.load()
        
        if not dataset:
            self._logger.warning("Golden dataset is empty")
            return ReplayMetrics(
                baseline_version=baseline_version,
                new_version=version,
                score_correlation=1.0,
                tier_agreement=1.0,
                outreach_quality_delta=0.0,
                false_positive_rate_delta=0.0,
                total_leads=0,
                score_diffs=[],
            )
        
        # Run new scoring on historical leads
        new_scores = []
        tier_matches = 0
        score_diffs = []
        
        for entry in dataset:
            # Create lead from input data
            lead = Lead(**entry.input_data)
            
            # Run new scoring
            new_result = scoring_func(lead)
            new_scores.append(new_result.final_score)
            
            # Compare to expected
            score_diffs.append(new_result.final_score - entry.expected_score)
            if new_result.lead_tier == entry.expected_tier:
                tier_matches += 1
        
        # Calculate metrics
        expected_scores = [e.expected_score for e in dataset]
        correlation = self._calculate_correlation(expected_scores, new_scores)
        tier_agreement = tier_matches / len(dataset)
        
        # Calculate false positive rate delta
        # (leads scored high but had bad outcomes)
        fp_baseline = self._calculate_false_positive_rate(dataset, expected_scores)
        fp_new = self._calculate_false_positive_rate(dataset, new_scores)
        
        return ReplayMetrics(
            baseline_version=baseline_version,
            new_version=version,
            score_correlation=correlation,
            tier_agreement=tier_agreement,
            outreach_quality_delta=0.0,  # Would need outreach comparison
            false_positive_rate_delta=fp_new - fp_baseline,
            total_leads=len(dataset),
            score_diffs=score_diffs,
        )
    
    def _calculate_correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        n = len(x)
        if n == 0:
            return 0.0
        
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        
        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        
        var_x = sum((xi - mean_x) ** 2 for xi in x)
        var_y = sum((yi - mean_y) ** 2 for yi in y)
        
        denominator = (var_x * var_y) ** 0.5
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    def _calculate_false_positive_rate(
        self,
        dataset: List[GoldenDatasetEntry],
        scores: List[int],
    ) -> float:
        """Calculate false positive rate (high score but bad outcome)."""
        false_positives = 0
        high_scores = 0
        
        for entry, score in zip(dataset, scores):
            if score >= 70:  # High score threshold
                high_scores += 1
                if entry.known_outcome == "no_response":
                    false_positives += 1
        
        if high_scores == 0:
            return 0.0
        
        return false_positives / high_scores


class ABTestFramework:
    """
    A/B testing framework.
    Requirements: 15.3, 15.4
    """
    
    def __init__(self):
        self._db = get_supabase_client()
        self._config = load_config()
        self._logger = logging.getLogger("zrai.eval.ab_test")
    
    def create_test(self, config: ABTestConfig) -> str:
        """Create a new A/B test."""
        test_id = str(uuid4())
        self._db.create_ab_test({
            "test_id": test_id,
            "name": config.name,
            "variants": config.variants,
            "metrics": config.metrics,
            "guardrails": config.guardrails,
            "sample_size": config.sample_size,
            "duration_days": config.duration_days,
            "status": "running",
            "created_at": datetime.utcnow().isoformat(),
        })
        return test_id
    
    def assign_variant(self, test_name: str, lead_id: UUID) -> str:
        """
        Assign a lead to a test variant.
        Requirements: 15.3
        """
        test = self._db.get_ab_test_by_name(test_name)
        if not test or test["status"] != "running":
            return "control"
        
        # Deterministic assignment based on lead_id
        # This ensures same lead always gets same variant
        hash_val = hash(str(lead_id) + test_name)
        
        variants = test["variants"]
        total_weight = sum(v.get("weight", 0.5) for v in variants)
        
        normalized = (hash_val % 1000) / 1000
        cumulative = 0
        
        for variant in variants:
            weight = variant.get("weight", 0.5) / total_weight
            cumulative += weight
            if normalized < cumulative:
                return variant["name"]
        
        return variants[-1]["name"]
    
    def record_metric(
        self,
        test_name: str,
        lead_id: UUID,
        variant: str,
        metric_name: str,
        value: float,
    ) -> None:
        """Record a metric for A/B test."""
        self._db.record_ab_metric({
            "test_name": test_name,
            "lead_id": str(lead_id),
            "variant": variant,
            "metric_name": metric_name,
            "value": value,
            "recorded_at": datetime.utcnow().isoformat(),
        })
    
    def evaluate_test(self, test_name: str) -> ABTestResult:
        """
        Evaluate A/B test results.
        Requirements: 15.3, 15.4
        """
        test = self._db.get_ab_test_by_name(test_name)
        if not test:
            raise ValueError(f"Test not found: {test_name}")
        
        metrics = self._db.get_ab_test_metrics(test_name)
        
        # Aggregate metrics by variant
        variant_metrics: Dict[str, Dict[str, List[float]]] = {}
        for m in metrics:
            variant = m["variant"]
            metric_name = m["metric_name"]
            
            if variant not in variant_metrics:
                variant_metrics[variant] = {}
            if metric_name not in variant_metrics[variant]:
                variant_metrics[variant][metric_name] = []
            
            variant_metrics[variant][metric_name].append(m["value"])
        
        # Calculate averages
        variant_a_metrics = {}
        variant_b_metrics = {}
        
        for variant, metrics_dict in variant_metrics.items():
            avg_metrics = {
                name: sum(values) / len(values) if values else 0
                for name, values in metrics_dict.items()
            }
            if variant == "control" or variant == "A":
                variant_a_metrics = avg_metrics
            else:
                variant_b_metrics = avg_metrics
        
        # Check guardrails
        should_rollback = False
        rollback_reason = None
        
        guardrails = test.get("guardrails", {})
        for metric, threshold in guardrails.items():
            if metric.startswith("min_"):
                actual_metric = metric[4:]
                if variant_b_metrics.get(actual_metric, 0) < threshold:
                    should_rollback = True
                    rollback_reason = f"{actual_metric} below minimum: {variant_b_metrics.get(actual_metric, 0)} < {threshold}"
                    break
            elif metric.startswith("max_"):
                actual_metric = metric[4:]
                if variant_b_metrics.get(actual_metric, 0) > threshold:
                    should_rollback = True
                    rollback_reason = f"{actual_metric} above maximum: {variant_b_metrics.get(actual_metric, 0)} > {threshold}"
                    break
        
        # Determine winner
        winner = None
        primary_metric = test.get("metrics", ["reply_rate"])[0]
        
        if not should_rollback:
            a_val = variant_a_metrics.get(primary_metric, 0)
            b_val = variant_b_metrics.get(primary_metric, 0)
            
            # Simple comparison (would use statistical significance in production)
            if b_val > a_val * 1.05:  # 5% improvement threshold
                winner = "treatment"
            elif a_val > b_val * 1.05:
                winner = "control"
            else:
                winner = "tie"
        
        return ABTestResult(
            test_name=test_name,
            variant_a_metrics=variant_a_metrics,
            variant_b_metrics=variant_b_metrics,
            winner=winner,
            should_rollback=should_rollback,
            rollback_reason=rollback_reason,
        )
    
    def rollback(self, test_name: str) -> None:
        """
        Rollback A/B test to control.
        Requirements: 15.4
        """
        self._logger.warning(f"Rolling back A/B test: {test_name}")
        self._db.update_ab_test(test_name, {
            "status": "rolled_back",
            "rolled_back_at": datetime.utcnow().isoformat(),
        })


class MetricsCalculator:
    """
    Calculate daily and aggregate metrics.
    Requirements: 14.2
    """
    
    def __init__(self):
        self._db = get_supabase_client()
        self._logger = logging.getLogger("zrai.eval.metrics")
    
    def calculate_daily_metrics(self, date: datetime) -> Dict[str, float]:
        """
        Calculate daily metrics.
        Requirements: 14.2
        """
        # Get outreach sent today
        outreach_sent = self._db.count_outreach_sent(date)
        
        # Get replies received
        replies = self._db.count_replies(date)
        
        # Get meetings booked
        meetings = self._db.count_meetings(date)
        
        # Get qualified leads
        qualified = self._db.count_qualified(date)
        
        # Get negative signals
        negative_signals = self._db.count_negative_signals(date)
        
        # Get human overrides
        human_overrides = self._db.count_human_overrides(date)
        
        # Get costs
        usage = self._db.get_usage_metrics(date)
        total_cost = (
            usage.get("llm_cost_usd", 0) +
            usage.get("browser_cost_usd", 0) +
            usage.get("scraper_cost_usd", 0)
        )
        
        # Calculate rates
        reply_rate = replies / outreach_sent if outreach_sent > 0 else 0
        meeting_rate = meetings / outreach_sent if outreach_sent > 0 else 0
        cost_per_meeting = total_cost / meetings if meetings > 0 else 0
        false_positive_rate = negative_signals / outreach_sent if outreach_sent > 0 else 0
        human_override_rate = human_overrides / qualified if qualified > 0 else 0
        
        metrics = {
            "date": date.isoformat(),
            "outreach_sent": outreach_sent,
            "replies": replies,
            "meetings": meetings,
            "qualified": qualified,
            "reply_rate": reply_rate,
            "meeting_rate": meeting_rate,
            "cost_per_qualified_meeting": cost_per_meeting,
            "false_positive_rate": false_positive_rate,
            "human_override_rate": human_override_rate,
            "total_cost_usd": total_cost,
        }
        
        # Store metrics
        self._db.store_daily_metrics(metrics)
        
        return metrics


class EvalAgent:
    """
    Main Eval Agent combining all evaluation functions.
    Requirements: 15
    """
    
    def __init__(self):
        self.golden_dataset = GoldenDataset()
        self.offline_replay = OfflineReplay()
        self.ab_framework = ABTestFramework()
        self.metrics_calculator = MetricsCalculator()
        self._logger = logging.getLogger("zrai.agents.eval")
    
    def run_daily_eval(self) -> Dict[str, Any]:
        """Run daily evaluation tasks."""
        today = datetime.utcnow()
        
        # Calculate daily metrics
        metrics = self.metrics_calculator.calculate_daily_metrics(today)
        
        # Check active A/B tests
        ab_results = []
        active_tests = self._get_active_tests()
        
        for test_name in active_tests:
            result = self.ab_framework.evaluate_test(test_name)
            ab_results.append(result)
            
            # Auto-rollback if needed
            if result.should_rollback:
                self.ab_framework.rollback(test_name)
                self._logger.warning(
                    f"Auto-rolled back test {test_name}: {result.rollback_reason}"
                )
        
        return {
            "daily_metrics": metrics,
            "ab_test_results": [
                {
                    "test_name": r.test_name,
                    "winner": r.winner,
                    "should_rollback": r.should_rollback,
                }
                for r in ab_results
            ],
        }
    
    def _get_active_tests(self) -> List[str]:
        """Get list of active A/B test names."""
        db = get_supabase_client()
        tests = db.get_active_ab_tests()
        return [t["name"] for t in tests]
    
    def process(self, state: LeadGraphState) -> LeadGraphState:
        """
        Process eval checks for a lead.
        This is called as a node in the graph.
        """
        # Eval agent typically runs separately, not per-lead
        # But can be used to assign A/B variants
        
        # Check for active A/B tests
        active_tests = self._get_active_tests()
        
        for test_name in active_tests:
            variant = self.ab_framework.assign_variant(test_name, state.lead_id)
            state.metadata[f"ab_test_{test_name}"] = variant
        
        return state


def eval_node(state: LeadGraphState) -> LeadGraphState:
    """LangGraph node function for eval."""
    agent = EvalAgent()
    return agent.process(state)
