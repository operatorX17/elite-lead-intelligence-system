"""
ZRAI GOLDMINE - The Ultimate Autonomous Sales Machine

This module contains the next-generation lead intelligence system that:
1. Discovers high-value prospects
2. Mystery shops them to prove they're losing money
3. Generates irrefutable proof decks
4. Executes autonomous multi-channel outreach
5. Books meetings and closes deals

Built with LangGraph for state management, parallel execution, and human-in-the-loop.
"""

from src.goldmine.state import GoldmineState
from src.goldmine.graph import create_goldmine_graph, run_goldmine_pipeline
from src.goldmine.mystery_shopper import MysteryShopperAgent
from src.goldmine.proof_generator import ProofGeneratorAgent
from src.goldmine.revenue_calculator import RevenueCalculator
from src.goldmine.steel_mystery_shopper import (
    SteelMysteryShopperInstructions,
    generate_mystery_shop_report,
    MYSTERY_IDENTITIES,
)
from src.goldmine.autonomous_engine import GoldmineEngine

__all__ = [
    "GoldmineState",
    "create_goldmine_graph",
    "run_goldmine_pipeline",
    "MysteryShopperAgent",
    "ProofGeneratorAgent",
    "RevenueCalculator",
    "SteelMysteryShopperInstructions",
    "generate_mystery_shop_report",
    "MYSTERY_IDENTITIES",
    "GoldmineEngine",
]
