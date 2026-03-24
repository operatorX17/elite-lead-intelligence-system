"""
Conversation Agent - stage-aware clinic sales conversations.
Requirements: 9.1-9.7
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import uuid4
import logging

from src.agents.base import BaseAgent
from src.agents.sales_playbook import (
    build_sales_fallback_response,
    build_sales_system_prompt,
    classify_sales_signals,
    infer_sales_stage,
    normalize_channel,
    should_escalate_to_human,
)
from src.graph.state import LeadGraphState
from src.db.models import Conversation, ConversationEntities, ConversationMessage
from src.tools.llm import get_llm_client


logger = logging.getLogger(__name__)


CONVERSATION_GUARDRAILS = {
    "no_pricing_negotiation": True,
    "max_price_range": {"min": 500, "max": 5000},
    "no_unverifiable_claims": True,
    "no_guarantees": True,
}


class ConversationAgent(BaseAgent):
    """
    Conversation Agent for AI-driven qualification and clinic-sales dialogue.

    The agent keeps the external conversation natural while tracking internal
    stage, objections, pain points, and handoff readiness.
    """

    def __init__(self):
        super().__init__("conversation")
        self._llm = get_llm_client()

    def process(self, state: LeadGraphState) -> LeadGraphState:
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

        channel = normalize_channel(metadata.get("channel"))
        conversation.transcript.append(
            ConversationMessage(
                role="prospect",
                message=prospect_message,
            )
        )

        entities = self._extract_entities(
            prospect_message,
            conversation.entities,
            channel=channel,
            lead=lead,
        )
        entities.current_channel = channel
        entities.stage = infer_sales_stage(entities.model_dump())
        conversation.entities = entities

        should_escalate, escalation_reasons = self._check_escalation_criteria(
            entities,
            prospect_message,
        )

        if entities.opt_out:
            state["is_escalated"] = False
            ai_response = build_sales_fallback_response(
                entities.model_dump(),
                metadata.get("intelligence") or metadata.get("analysis_bundle") or {},
            )
            conversation.transcript.append(
                ConversationMessage(
                    role="ai",
                    message=ai_response,
                )
            )
            metadata["last_ai_response"] = ai_response
            metadata["conversation_stage"] = entities.stage
            metadata["conversation_opt_out"] = True
        elif should_escalate:
            conversation.escalated = True
            conversation.escalated_at = datetime.utcnow()
            state["is_escalated"] = True
            conversation.objection_summary = self._generate_objection_summary(
                entities,
                escalation_reasons,
            )
            conversation.suggested_close_angle = self._generate_close_angle(lead, entities)
            metadata["objection_summary"] = conversation.objection_summary
            metadata["suggested_close_angle"] = conversation.suggested_close_angle
            metadata["conversation_stage"] = entities.stage
            metadata["conversation_handoff_reason"] = escalation_reasons
        else:
            state["is_escalated"] = False
            try:
                ai_response = self._generate_response(
                    conversation,
                    lead,
                    prospect_message,
                    metadata.get("intelligence") or metadata.get("analysis_bundle") or {},
                    channel,
                )
            except Exception as exc:
                self._logger.error(f"Conversation response generation error: {exc}")
                ai_response = build_sales_fallback_response(
                    entities.model_dump(),
                    metadata.get("intelligence") or metadata.get("analysis_bundle") or {},
                )

            conversation.transcript.append(
                ConversationMessage(
                    role="ai",
                    message=ai_response,
                )
            )
            metadata["last_ai_response"] = ai_response
            metadata["conversation_stage"] = entities.stage

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

        self._save_conversation(conversation)
        return state

    def _hydrate_transcript(
        self,
        transcript: List[Dict[str, Any]],
    ) -> List[ConversationMessage]:
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
        if not entities:
            return ConversationEntities()
        try:
            confidence = float(entities.get("confidence") or 0.5)
        except (TypeError, ValueError):
            confidence = 0.5
        return ConversationEntities(
            budget_range=entities.get("budget_range"),
            role=entities.get("role"),
            timeline=entities.get("timeline"),
            objections=entities.get("objections") or [],
            objection_categories=entities.get("objection_categories") or [],
            pain_confirmed=bool(entities.get("pain_confirmed")),
            pain_points=entities.get("pain_points") or [],
            pain_summary=entities.get("pain_summary"),
            interest_level=entities.get("interest_level") or "medium",
            stage=entities.get("stage") or "NEW",
            current_channel=entities.get("current_channel"),
            channel_history=entities.get("channel_history") or [],
            lead_channels=entities.get("lead_channels") or [],
            clinic_type=entities.get("clinic_type"),
            current_reply_owner=entities.get("current_reply_owner"),
            decision_maker_confirmed=bool(entities.get("decision_maker_confirmed")),
            decision_maker_role=entities.get("decision_maker_role"),
            response_speed_status=entities.get("response_speed_status"),
            follow_up_consistency=entities.get("follow_up_consistency"),
            appointment_no_show_risk=entities.get("appointment_no_show_risk"),
            goal_focus=entities.get("goal_focus"),
            requested_next_step=entities.get("requested_next_step"),
            preferred_time=entities.get("preferred_time"),
            handoff_requested=bool(entities.get("handoff_requested")),
            pilot_interest=bool(entities.get("pilot_interest")),
            payment_interest=bool(entities.get("payment_interest")),
            integration_needs=entities.get("integration_needs") or [],
            compliance_concerns=entities.get("compliance_concerns") or [],
            current_tools=entities.get("current_tools") or [],
            confidence=max(0.0, min(confidence, 1.0)),
            last_intent=entities.get("last_intent"),
            next_best_question=entities.get("next_best_question"),
            opt_out=bool(entities.get("opt_out")),
        )

    def _extract_entities(
        self,
        message: str,
        existing_entities: ConversationEntities,
        *,
        channel: str,
        lead: Dict[str, Any],
    ) -> ConversationEntities:
        analysis_role = str(lead.get("category") or "clinic")
        prompt = f"""
Extract lightweight clinic-sales conversation state from this prospect message.

Message: "{message}"

Known context:
- Clinic/business type: {analysis_role}
- Existing role: {existing_entities.role}
- Existing timeline: {existing_entities.timeline}
- Existing objections: {existing_entities.objections}
- Existing pain points: {existing_entities.pain_points}
- Existing stage: {existing_entities.stage}

Return only information that is actually implied by the message.
Do not invent certainty.
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
                "objection_categories": {"type": "array", "items": {"type": "string"}},
                "pain_confirmed": {"type": "boolean"},
                "pain_points": {"type": "array", "items": {"type": "string"}},
                "pain_summary": {"type": "string"},
                "interest_level": {"type": "string", "enum": ["high", "medium", "low"]},
                "lead_channels": {"type": "array", "items": {"type": "string"}},
                "current_reply_owner": {"type": "string"},
                "decision_maker_confirmed": {"type": "boolean"},
                "decision_maker_role": {"type": "string"},
                "response_speed_status": {"type": "string"},
                "follow_up_consistency": {"type": "string"},
                "appointment_no_show_risk": {"type": "string"},
                "goal_focus": {"type": "string"},
                "requested_next_step": {"type": "string"},
                "preferred_time": {"type": "string"},
                "handoff_requested": {"type": "boolean"},
                "pilot_interest": {"type": "boolean"},
                "payment_interest": {"type": "boolean"},
                "integration_needs": {"type": "array", "items": {"type": "string"}},
                "compliance_concerns": {"type": "array", "items": {"type": "string"}},
                "current_tools": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "number"},
                "last_intent": {"type": "string"},
                "next_best_question": {"type": "string"},
                "opt_out": {"type": "boolean"},
            },
        }

        extracted: Dict[str, Any] = {}
        try:
            extracted = self._llm.generate_structured(prompt, schema)
        except Exception as exc:
            self._logger.error(f"Entity extraction error: {exc}")

        heuristics = classify_sales_signals(message)
        extracted = {
            **extracted,
            "lead_channels": self._merge_unique_list(
                extracted.get("lead_channels") or [],
                heuristics.get("lead_channels") or [],
            ),
            "objection_categories": self._merge_unique_list(
                extracted.get("objection_categories") or [],
                heuristics.get("objection_categories") or [],
            ),
            "pain_points": self._merge_unique_list(
                extracted.get("pain_points") or [],
                heuristics.get("pain_points") or [],
            ),
            "opt_out": bool(extracted.get("opt_out") or heuristics.get("opt_out")),
            "handoff_requested": bool(
                extracted.get("handoff_requested") or heuristics.get("handoff_requested")
            ),
            "payment_interest": bool(
                extracted.get("payment_interest") or heuristics.get("payment_interest")
            ),
            "role": extracted.get("role") or heuristics.get("role"),
            "requested_next_step": extracted.get("requested_next_step")
            or heuristics.get("requested_next_step"),
        }

        existing_entities.current_channel = channel
        existing_entities.channel_history = self._merge_unique_list(
            existing_entities.channel_history,
            [channel],
        )
        existing_entities.lead_channels = self._merge_unique_list(
            existing_entities.lead_channels,
            extracted.get("lead_channels") or [],
        )

        if extracted.get("budget_range"):
            existing_entities.budget_range = extracted["budget_range"]
        if extracted.get("role"):
            existing_entities.role = extracted["role"]
        if extracted.get("timeline"):
            existing_entities.timeline = extracted["timeline"]
        if extracted.get("pain_summary"):
            existing_entities.pain_summary = extracted["pain_summary"]
        if extracted.get("interest_level"):
            existing_entities.interest_level = extracted["interest_level"]
        if extracted.get("current_reply_owner"):
            existing_entities.current_reply_owner = extracted["current_reply_owner"]
        if extracted.get("decision_maker_role"):
            existing_entities.decision_maker_role = extracted["decision_maker_role"]
        if extracted.get("response_speed_status"):
            existing_entities.response_speed_status = extracted["response_speed_status"]
        if extracted.get("follow_up_consistency"):
            existing_entities.follow_up_consistency = extracted["follow_up_consistency"]
        if extracted.get("appointment_no_show_risk"):
            existing_entities.appointment_no_show_risk = extracted["appointment_no_show_risk"]
        if extracted.get("goal_focus"):
            existing_entities.goal_focus = extracted["goal_focus"]
        if extracted.get("requested_next_step"):
            existing_entities.requested_next_step = extracted["requested_next_step"]
        if extracted.get("preferred_time"):
            existing_entities.preferred_time = extracted["preferred_time"]
        if extracted.get("confidence") is not None:
            try:
                existing_entities.confidence = max(
                    0.0,
                    min(float(extracted["confidence"]), 1.0),
                )
            except (TypeError, ValueError):
                pass
        if extracted.get("last_intent"):
            existing_entities.last_intent = extracted["last_intent"]
        if extracted.get("next_best_question"):
            existing_entities.next_best_question = extracted["next_best_question"]

        if extracted.get("objections"):
            existing_entities.objections = self._merge_unique_list(
                existing_entities.objections,
                extracted["objections"],
            )
        if extracted.get("objection_categories"):
            existing_entities.objection_categories = self._merge_unique_list(
                existing_entities.objection_categories,
                extracted["objection_categories"],
            )
        if extracted.get("pain_points"):
            existing_entities.pain_points = self._merge_unique_list(
                existing_entities.pain_points,
                extracted["pain_points"],
            )
        if extracted.get("integration_needs"):
            existing_entities.integration_needs = self._merge_unique_list(
                existing_entities.integration_needs,
                extracted["integration_needs"],
            )
        if extracted.get("compliance_concerns"):
            existing_entities.compliance_concerns = self._merge_unique_list(
                existing_entities.compliance_concerns,
                extracted["compliance_concerns"],
            )
        if extracted.get("current_tools"):
            existing_entities.current_tools = self._merge_unique_list(
                existing_entities.current_tools,
                extracted["current_tools"],
            )

        if extracted.get("pain_confirmed") or existing_entities.pain_points:
            existing_entities.pain_confirmed = True
        if extracted.get("decision_maker_confirmed") or (
            existing_entities.role and existing_entities.role.lower() in {
                "owner",
                "founder",
                "doctor",
                "manager",
                "director",
            }
        ):
            existing_entities.decision_maker_confirmed = True
        if extracted.get("handoff_requested"):
            existing_entities.handoff_requested = True
        if extracted.get("pilot_interest"):
            existing_entities.pilot_interest = True
        if extracted.get("payment_interest"):
            existing_entities.payment_interest = True
        if extracted.get("opt_out"):
            existing_entities.opt_out = True

        return existing_entities

    def _check_escalation_criteria(
        self,
        entities: ConversationEntities,
        prospect_message: str,
    ) -> tuple[bool, List[str]]:
        entity_dict = entities.model_dump()
        if entities.opt_out:
            return False, ["Lead opted out"]
        should_escalate, reasons = should_escalate_to_human(entity_dict)
        return should_escalate, reasons

    def _generate_response(
        self,
        conversation: Conversation,
        lead: Dict[str, Any],
        prospect_message: str,
        analysis_bundle: Optional[Dict[str, Any]] = None,
        channel: str = "email",
    ) -> str:
        entities = conversation.entities
        transcript_text = "\n".join(
            f"{msg.role.upper()}: {msg.message}"
            for msg in conversation.transcript[-6:]
        )

        missing_info = self._build_missing_info(entities)
        system_prompt = build_sales_system_prompt(
            lead=lead,
            entities=entities.model_dump(),
            analysis_bundle=analysis_bundle,
            missing_info=missing_info,
            channel=channel,
        )
        prompt = f"""
Conversation so far:
{transcript_text}

Latest prospect message:
{prospect_message}

Write the next reply.
Requirements:
- Sound like a sharp human operator for clinics
- 1 short message for email/linkedin, or 1-3 short chat bubbles worth of text for messaging channels
- No markdown
- No bullet points
- Do not pitch too early
- Move the conversation one step forward with one question or one clear next step
"""

        response = self._llm.generate(
            prompt,
            system_prompt=system_prompt,
            temperature=0.45,
            max_tokens=220,
        )
        return response.strip()

    def _build_missing_info(self, entities: ConversationEntities) -> List[str]:
        missing: List[str] = []
        if not entities.pain_confirmed:
            missing.append("confirmed pain point")
        if not entities.decision_maker_confirmed:
            missing.append("decision-maker ownership")
        if not entities.lead_channels:
            missing.append("current enquiry channels")
        if not entities.follow_up_consistency:
            missing.append("follow-up consistency")
        if not entities.requested_next_step and entities.stage in {"QUALIFIED", "PAIN_FOUND", "PROOF_SHARED"}:
            missing.append("preferred next step")
        return missing

    def _merge_unique_list(self, left: List[Any], right: List[Any]) -> List[str]:
        seen = set()
        merged: List[str] = []
        for value in [*(left or []), *(right or [])]:
            normalized = str(value or "").strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(normalized)
        return merged

    def _generate_objection_summary(
        self,
        entities: ConversationEntities,
        escalation_reasons: Optional[List[str]] = None,
    ) -> str:
        summary_bits: List[str] = []
        if entities.objection_categories:
            summary_bits.append(
                f"Objection categories: {', '.join(entities.objection_categories)}"
            )
        if entities.objections:
            summary_bits.append(f"Verbatim objections: {', '.join(entities.objections)}")
        if escalation_reasons:
            summary_bits.append(f"Handoff reason: {', '.join(escalation_reasons)}")
        return " | ".join(summary_bits) if summary_bits else "No significant objections raised."

    def _generate_close_angle(
        self,
        lead: Dict[str, Any],
        entities: ConversationEntities,
    ) -> str:
        angles: List[str] = []
        category = str(lead.get("category") or "clinic")
        if entities.pain_confirmed:
            angles.append(f"Lead acknowledged a {category} conversion/follow-up gap")
        if entities.lead_channels:
            angles.append(f"Channels in play: {', '.join(entities.lead_channels)}")
        if entities.follow_up_consistency:
            angles.append(f"Follow-up status: {entities.follow_up_consistency}")
        if entities.requested_next_step:
            angles.append(f"Requested next step: {entities.requested_next_step}")
        if entities.payment_interest:
            angles.append("Commercial intent is active")
        if entities.objection_categories:
            angles.append(f"Handle objection: {', '.join(entities.objection_categories)}")
        return " | ".join(angles) if angles else "Keep the conversation consultative and diagnostic."

    def _save_conversation(self, conversation: Conversation) -> None:
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
        data["transcript"] = [
            {
                "role": msg.role,
                "message": msg.message,
                "timestamp": msg.timestamp.isoformat()
                if hasattr(msg.timestamp, "isoformat")
                else str(msg.timestamp),
            }
            for msg in conversation.transcript
        ]
        data["entities"] = conversation.entities.model_dump()

        existing = self._db.get_conversation(conversation.conversation_id)
        if existing:
            self._db.update_conversation(conversation.conversation_id, data)
        else:
            data["created_at"] = datetime.utcnow().isoformat()
            self._db.create_conversation(data)


_conversation_agent = ConversationAgent()


def conversation_node(state: LeadGraphState) -> LeadGraphState:
    return _conversation_agent(state)
