"""
Conversation Agent - AI qualification conversations.
Requirements: 9.1-9.7
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4
import logging

from src.agents.base import BaseAgent
from src.graph.state import LeadGraphState
from src.db.models import (
    Conversation, ConversationMessage, ConversationEntities
)
from src.tools.llm import get_llm_client


logger = logging.getLogger(__name__)


# Hard stop rules (Requirements 9.6, 9.7)
CONVERSATION_GUARDRAILS = {
    "no_pricing_negotiation": True,
    "max_price_range": {"min": 500, "max": 5000},
    "no_unverifiable_claims": True,
    "no_guarantees": True,
    "escalate_on_objection": ["price", "competitor", "timing"],
}

# Discovery questions
DISCOVERY_QUESTIONS = [
    "How do you currently handle missed calls?",
    "What percentage of leads do you think get contacted within 5 minutes?",
    "Do you have a system for following up on leads that didn't respond?",
    "What's your biggest challenge with lead follow-up right now?",
    "How many leads do you typically get per month?",
]


class ConversationAgent(BaseAgent):
    """
    Conversation Agent for AI-driven qualification.
    
    Requirements:
    - 9.1: Engage in qualification dialogue following strict escalation policy
    - 9.2: Confirm budget, authority, and timeline before escalation
    - 9.3: Store full conversation transcript
    - 9.4: Capture budget_range, role, timeline, objections as structured entities
    - 9.5: Generate objection_summary and suggested_close_angle
    - 9.6: Enforce hard stop rules preventing negotiation beyond ranges
    - 9.7: Enforce hard stop rules preventing unverifiable claims
    """
    
    def __init__(self):
        super().__init__("conversation")
        self._llm = get_llm_client()
    
    def process(self, state: LeadGraphState) -> LeadGraphState:
        """Process conversation for a lead."""
        if not state.get("lead"):
            self._logger.warning("No lead data for conversation")
            return state
        
        state["current_stage"] = "conversation"
        
        if not state.get("conversation_transcript"):
            state["conversation_transcript"] = []
        if not state.get("conversation_entities"):
            state["conversation_entities"] = {}

        incoming_message = (state.get("metadata") or {}).get("incoming_message")
        if incoming_message:
            return self.handle_reply(state, incoming_message)
        
        return state
    
    def handle_reply(
        self,
        state: LeadGraphState,
        prospect_message: str,
    ) -> LeadGraphState:
        """
        Handle a reply from the prospect.
        Requirements: 9.1, 9.3, 9.4
        """
        metadata = state.setdefault("metadata", {})
        lead = state.get("lead") or {}
        lead_id = lead.get("lead_id")

        if not lead_id:
            self._logger.warning("Missing lead_id for conversation reply")
            return state

        transcript = self._hydrate_transcript(state.get("conversation_transcript") or [])
        entities = self._hydrate_entities(state.get("conversation_entities") or {})
        conversation = Conversation(
            conversation_id=metadata.get("conversation_id") or uuid4(),
            lead_id=lead_id,
            transcript=transcript,
            entities=entities,
        )

        # Add prospect message to transcript
        conversation.transcript.append(ConversationMessage(
            role="prospect",
            message=prospect_message,
        ))
        
        # Extract entities from message
        entities = self._extract_entities(prospect_message, conversation.entities)
        conversation.entities = entities
        
        # Check for escalation criteria
        should_escalate = self._check_escalation_criteria(entities)
        
        if should_escalate:
            conversation.escalated = True
            conversation.escalated_at = datetime.utcnow()
            state["is_escalated"] = True
            
            # Generate objection summary and close angle
            conversation.objection_summary = self._generate_objection_summary(entities)
            conversation.suggested_close_angle = self._generate_close_angle(lead, entities)
            metadata["objection_summary"] = conversation.objection_summary
            metadata["suggested_close_angle"] = conversation.suggested_close_angle
        else:
            state["is_escalated"] = False
            # Generate AI response
            try:
                ai_response = self._generate_response(
                    conversation,
                    lead,
                    prospect_message,
                    metadata.get("intelligence") or metadata.get("analysis_bundle") or {},
                )
            except Exception as exc:
                self._logger.error(f"Conversation response generation error: {exc}")
                ai_response = self._generate_fallback_response(entities)
            
            # Add AI response to transcript
            conversation.transcript.append(ConversationMessage(
                role="ai",
                message=ai_response,
            ))
            metadata["last_ai_response"] = ai_response
        
        metadata["conversation_id"] = str(conversation.conversation_id)
        state["conversation_transcript"] = [
            {
                "role": message.role,
                "message": message.message,
                "timestamp": message.timestamp.isoformat()
                if hasattr(message.timestamp, "isoformat")
                else str(message.timestamp),
            }
            for message in conversation.transcript
        ]
        state["conversation_entities"] = conversation.entities.model_dump()

        # Save conversation
        self._save_conversation(conversation)
        
        return state

    def _hydrate_transcript(
        self,
        transcript: List[Dict[str, Any]],
    ) -> List[ConversationMessage]:
        """Convert serialized transcript items into ConversationMessage objects."""
        hydrated: List[ConversationMessage] = []
        for item in transcript:
            timestamp = item.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    timestamp = datetime.utcnow()
            hydrated.append(
                ConversationMessage(
                    role=item.get("role", "prospect"),
                    message=item.get("message", ""),
                    timestamp=timestamp or datetime.utcnow(),
                )
            )
        return hydrated

    def _hydrate_entities(
        self,
        entities: Dict[str, Any],
    ) -> ConversationEntities:
        """Convert serialized entity data into a ConversationEntities model."""
        if not entities:
            return ConversationEntities()
        return ConversationEntities(
            budget_range=entities.get("budget_range"),
            role=entities.get("role"),
            timeline=entities.get("timeline"),
            objections=entities.get("objections") or [],
            pain_confirmed=bool(entities.get("pain_confirmed")),
            interest_level=entities.get("interest_level") or "medium",
        )
    
    def _extract_entities(
        self,
        message: str,
        existing_entities: ConversationEntities,
    ) -> ConversationEntities:
        """
        Extract structured entities from message.
        Requirements: 9.4
        """
        # Use LLM to extract entities
        prompt = f"""
Extract the following information from this prospect message if present:
- Budget range (min and max in USD)
- Role/title of the person
- Timeline for making a decision
- Any objections mentioned
- Whether they confirmed a pain point
- Interest level (high, medium, low)

Message: "{message}"

Existing context:
- Budget: {existing_entities.budget_range}
- Role: {existing_entities.role}
- Timeline: {existing_entities.timeline}
- Objections: {existing_entities.objections}
- Pain confirmed: {existing_entities.pain_confirmed}
"""
        
        schema = {
            "type": "object",
            "properties": {
                "budget_range": {
                    "type": "object",
                    "properties": {
                        "min": {"type": "integer"},
                        "max": {"type": "integer"},
                    },
                },
                "role": {"type": "string"},
                "timeline": {"type": "string"},
                "objections": {"type": "array", "items": {"type": "string"}},
                "pain_confirmed": {"type": "boolean"},
                "interest_level": {"type": "string", "enum": ["high", "medium", "low"]},
            },
        }
        
        try:
            extracted = self._llm.generate_structured(prompt, schema)
            
            # Merge with existing entities
            if extracted.get("budget_range"):
                existing_entities.budget_range = extracted["budget_range"]
            if extracted.get("role"):
                existing_entities.role = extracted["role"]
            if extracted.get("timeline"):
                existing_entities.timeline = extracted["timeline"]
            if extracted.get("objections"):
                existing_entities.objections.extend(extracted["objections"])
                existing_entities.objections = list(set(existing_entities.objections))
            if extracted.get("pain_confirmed"):
                existing_entities.pain_confirmed = True
            if extracted.get("interest_level"):
                existing_entities.interest_level = extracted["interest_level"]
                
        except Exception as e:
            self._logger.error(f"Entity extraction error: {e}")
        
        return existing_entities
    
    def _check_escalation_criteria(
        self,
        entities: ConversationEntities,
    ) -> bool:
        """
        Check if escalation criteria are met.
        Requirements: 9.2
        
        BANT criteria:
        - Budget: Confirmed budget range or willingness to invest
        - Authority: Decision-maker or can influence decision
        - Need: Pain point acknowledged
        - Timeline: Timeframe for implementation
        """
        has_budget = entities.budget_range is not None
        has_authority = entities.role in ["owner", "decision_maker", "manager", "director", "ceo", "founder"]
        has_need = entities.pain_confirmed
        has_timeline = entities.timeline is not None
        
        # Escalate if BANT is complete
        if has_budget and has_authority and has_need and has_timeline:
            return True
        
        # Also escalate on certain objections
        for objection in entities.objections:
            objection_lower = objection.lower()
            for trigger in CONVERSATION_GUARDRAILS["escalate_on_objection"]:
                if trigger in objection_lower:
                    return True
        
        return False
    
    def _generate_response(
        self,
        conversation: Conversation,
        lead: Dict[str, Any],
        prospect_message: str,
        analysis_bundle: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate AI response following guardrails.
        Requirements: 9.1, 9.6, 9.7
        """
        entities = conversation.entities
        
        # Build context from conversation
        transcript_text = "\n".join([
            f"{msg.role.upper()}: {msg.message}"
            for msg in conversation.transcript[-5:]  # Last 5 messages
        ])
        
        # Determine what to ask next
        missing_info = []
        if not entities.pain_confirmed:
            missing_info.append("pain point confirmation")
        if not entities.budget_range:
            missing_info.append("budget")
        if not entities.role:
            missing_info.append("role/authority")
        if not entities.timeline:
            missing_info.append("timeline")

        analysis_bundle = analysis_bundle or {}
        facts = analysis_bundle.get("facts") or {}
        guidance = analysis_bundle.get("guidance") or {}
        agent_context = analysis_bundle.get("agent_context") or {}
        intelligence_lines: List[str] = []
        if agent_context.get("business_summary"):
            intelligence_lines.append(f"Business context: {agent_context.get('business_summary')}")
        if agent_context.get("conversion_summary"):
            intelligence_lines.append(f"Conversion context: {agent_context.get('conversion_summary')}")
        if guidance.get("site_truth_summary"):
            intelligence_lines.append(f"Site truth: {guidance.get('site_truth_summary')}")
        if guidance.get("top_issue"):
            intelligence_lines.append(f"Top issue: {guidance.get('top_issue')}")
        if guidance.get("next_best_action"):
            intelligence_lines.append(f"Next best action: {guidance.get('next_best_action')}")
        if agent_context.get("recommended_offer"):
            intelligence_lines.append(f"Recommended offer: {agent_context.get('recommended_offer')}")
        if facts.get("recommended_channel"):
            intelligence_lines.append(f"Preferred channel: {facts.get('recommended_channel')}")
        
        system_prompt = f"""You are a helpful sales assistant qualifying leads for a lead capture optimization service for {lead.get('business_name', 'this lead')}.

HARD RULES (NEVER BREAK):
1. NEVER negotiate on price below ${CONVERSATION_GUARDRAILS['max_price_range']['min']}
2. NEVER make unverifiable claims or guarantees
3. NEVER promise specific results without data
4. If asked about pricing, give a range of ${CONVERSATION_GUARDRAILS['max_price_range']['min']}-${CONVERSATION_GUARDRAILS['max_price_range']['max']}
5. Be helpful but don't be pushy

Your goal is to:
1. Acknowledge their message
2. Ask a discovery question to learn more about their needs
3. Keep responses concise (2-3 sentences max)

Missing information to gather: {', '.join(missing_info) if missing_info else 'All key info gathered'}

Use the verified business intelligence below when relevant. Do not invent facts beyond it.
{chr(10).join(intelligence_lines) if intelligence_lines else 'No verified analysis context available.'}
"""
        
        prompt = f"""
Conversation so far:
{transcript_text}

PROSPECT: {prospect_message}

Generate a helpful, concise response. Remember the hard rules.
"""
        
        response = self._llm.generate(
            prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=200,
        )
        
        return response.strip()

    def _generate_fallback_response(
        self,
        entities: ConversationEntities,
    ) -> str:
        """Return a deterministic fallback when the LLM provider fails."""
        if not entities.pain_confirmed:
            return "Understood. What is the biggest bottleneck in your current lead follow-up process?"
        if not entities.role:
            return "Thanks for the context. Are you the person who would own this decision internally?"
        if not entities.timeline:
            return "Helpful. What timeline are you working toward for improving this workflow?"
        if not entities.budget_range:
            return "That makes sense. Do you already have a budget range in mind for solving this?"
        return "Thanks, that gives me enough context. I can outline the next step and a recommended approach from here."
    
    def _generate_objection_summary(
        self,
        entities: ConversationEntities,
    ) -> str:
        """
        Generate objection summary.
        Requirements: 9.5
        """
        if not entities.objections:
            return "No significant objections raised."
        
        return f"Objections raised: {', '.join(entities.objections)}"
    
    def _generate_close_angle(
        self,
        lead,
        entities: ConversationEntities,
    ) -> str:
        """
        Generate suggested close angle.
        Requirements: 9.5
        """
        angles = []
        
        if entities.pain_confirmed:
            angles.append("Lead has confirmed pain point - emphasize solution")
        
        if entities.budget_range:
            budget_mid = (entities.budget_range.get("min", 0) + entities.budget_range.get("max", 0)) / 2
            if budget_mid >= 1000:
                angles.append("Budget is healthy - can propose full solution")
            else:
                angles.append("Budget is tight - propose starter package")
        
        if entities.timeline:
            if "asap" in entities.timeline.lower() or "urgent" in entities.timeline.lower():
                angles.append("Urgent timeline - emphasize quick implementation")
            elif "month" in entities.timeline.lower():
                angles.append("Monthly timeline - standard onboarding")
        
        if "price" in " ".join(entities.objections).lower():
            angles.append("Price sensitive - emphasize ROI and value")
        
        if "competitor" in " ".join(entities.objections).lower():
            angles.append("Considering competitors - differentiate on service/results")
        
        return " | ".join(angles) if angles else "Standard qualification approach"
    
    def _save_conversation(self, conversation: Conversation) -> None:
        """Save conversation to database."""
        data = conversation.model_dump()
        data["conversation_id"] = str(conversation.conversation_id)
        data["lead_id"] = str(conversation.lead_id)
        data["created_at"] = conversation.created_at.isoformat()
        data["updated_at"] = datetime.utcnow().isoformat()
        data["escalated_at"] = (
            conversation.escalated_at.isoformat()
            if conversation.escalated_at
            else None
        )
        
        # Convert transcript to JSON-serializable format
        data["transcript"] = [
            {
                "role": msg.role,
                "message": msg.message,
                "timestamp": msg.timestamp.isoformat() if hasattr(msg.timestamp, 'isoformat') else str(msg.timestamp),
            }
            for msg in conversation.transcript
        ]
        
        # Convert entities to dict
        data["entities"] = {
            "budget_range": conversation.entities.budget_range,
            "role": conversation.entities.role,
            "timeline": conversation.entities.timeline,
            "objections": conversation.entities.objections,
            "pain_confirmed": conversation.entities.pain_confirmed,
            "interest_level": conversation.entities.interest_level,
        }
        
        # Check if conversation exists
        existing = self._db.get_conversation(conversation.conversation_id)
        if existing:
            self._db.update_conversation(conversation.conversation_id, data)
        else:
            data["created_at"] = datetime.utcnow().isoformat()
            self._db.create_conversation(data)


# Create singleton instance for LangGraph node
_conversation_agent = ConversationAgent()


def conversation_node(state: LeadGraphState) -> LeadGraphState:
    """LangGraph node function for conversation."""
    return _conversation_agent(state)
