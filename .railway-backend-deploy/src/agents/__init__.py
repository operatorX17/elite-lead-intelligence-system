"""Agent nodes for ZRAI Lead OS LangGraph.

Keep imports lazy so importing one submodule does not eagerly construct every
agent and all of their external clients during API startup.
"""

from importlib import import_module
from typing import Any


_NODE_MODULES = {
    "discovery_node": ".discovery",
    "enrichment_node": ".enrichment",
    "intent_node": ".intent",
    "audit_node": ".audit",
    "scoring_node": ".scoring",
    "outreach_node": ".outreach",
    "conversation_node": ".conversation",
    "governance_node": ".governance",
    "eval_node": ".eval",
}


def __getattr__(name: str) -> Any:
    module_name = _NODE_MODULES.get(name)
    if not module_name:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    return getattr(module, name)


__all__ = list(_NODE_MODULES)
