"""
AI Reasoning Agent - The Supreme Validator
Verifies all data, detects bullshit, and ensures only REAL intelligence passes through
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class ReasoningResult:
    """Result of AI reasoning analysis"""
    is_valid: bool
    confidence: float  # 0.0 to 1.0
    reasoning: str
    issues_found: List[str]
    corrections: Dict[str, Any]
    final_verdict: str  # "ACCEPT", "REJECT", "NEEDS_REVIEW"


class ReasoningAgent:
    """
    Supreme AI Reasoning Agent
    
    This agent is the FINAL JUDGE. It:
    1. Validates all enrichment data is REAL (not fallback)
    2. Verifies contact info is actually present
    3. Checks if scoring logic makes sense
    4. Detects contradictions and bullshit
    5. Provides detailed reasoning for every decision
    """
    
    def __init__(self, llm_client):
        self.llm = llm_client
        logger.info("[REASONING AGENT] Initialized - Supreme Validator Active")
    
    async def validate_lead(self, lead: Dict[str, Any]) -> ReasoningResult:
        """
        Validate a lead with AI reasoning
        
        This is the SUPREME VALIDATION that catches all bullshit
        """
        
        logger.info(f"[REASONING] Validating lead: {lead.get('business_name')}")
        
        # Step 1: Check data quality
        data_quality = self._check_data_quality(lead)
        
        # Step 2: Check reachability
        reachability = self._check_reachability(lead)
        
        # Step 3: Check opportunity signals
        opportunity = self._check_opportunity(lead)
        
        # Step 4: Use LLM for deep reasoning
        llm_analysis = await self._llm_deep_analysis(lead, data_quality, reachability, opportunity)
        
        # Step 5: Make final decision
        result = self._make_final_decision(lead, data_quality, reachability, opportunity, llm_analysis)
        
        logger.info(f"[REASONING] Verdict: {result.final_verdict} (confidence: {result.confidence:.2f})")
        logger.info(f"[REASONING] Reasoning: {result.reasoning}")
        
        return result
    
    def _check_data_quality(self, lead: Dict) -> Dict[str, Any]:
        """Check if we have REAL data or just fallback assumptions"""
        
        issues = []
        quality_score = 100
        
        # Check enrichment status
        status = lead.get("status", "unknown")
        if status == "fallback":
            issues.append("Enrichment FAILED - using fallback assumptions (NOT REAL DATA)")
            quality_score -= 50
        elif status == "no_website":
            issues.append("No website found - cannot enrich")
            quality_score -= 40
        elif status == "firecrawl_success":
            # Good! Real data
            pass
        else:
            issues.append(f"Unknown enrichment status: {status}")
            quality_score -= 30
        
        # Check if we have actual contact info
        has_real_email = len(lead.get("emails", [])) > 0
        has_real_phone = len(lead.get("phones", [])) > 0
        
        if not has_real_email and not has_real_phone:
            issues.append("NO contact info extracted (emails=[], phones=[])")
            quality_score -= 30
        
        # Check if signals are detected or assumed
        if not lead.get("has_booking_system") and not lead.get("has_whatsapp"):
            if status == "fallback":
                issues.append("Booking/WhatsApp signals are ASSUMED (not detected)")
                quality_score -= 20
        
        return {
            "quality_score": max(0, quality_score),
            "issues": issues,
            "has_real_data": status == "firecrawl_success",
            "has_contact_info": has_real_email or has_real_phone
        }
    
    def _check_reachability(self, lead: Dict) -> Dict[str, Any]:
        """Check if we can actually REACH this business"""
        
        issues = []
        reachability_score = 0
        
        # Website check
        website = lead.get("website")
        if website:
            reachability_score += 30
        else:
            issues.append("NO WEBSITE - business is unreachable online")
        
        # Phone check
        phone = lead.get("phone")
        if phone:
            reachability_score += 25
        else:
            issues.append("NO PHONE - cannot call")
        
        # Email check
        emails = lead.get("emails", [])
        if len(emails) > 0:
            reachability_score += 25
        else:
            issues.append("NO EMAIL - cannot send messages")
        
        # Social check
        social_links = lead.get("social_links", {})
        if len(social_links) > 0:
            reachability_score += 10
        
        # WhatsApp check
        if lead.get("has_whatsapp"):
            reachability_score += 10
        
        return {
            "reachability_score": reachability_score,
            "issues": issues,
            "is_reachable": reachability_score >= 30  # Need at least website OR phone+email
        }
    
    def _check_opportunity(self, lead: Dict) -> Dict[str, Any]:
        """Check if there's REAL opportunity (not just missing features)"""
        
        opportunity_signals = []
        opportunity_score = 0
        
        # POSITIVE signals (business is active and has volume)
        # INCREASED: Website is critical for Indian healthcare businesses
        if lead.get("website"):
            opportunity_signals.append("Has website - active online presence")
            opportunity_score += 30  # INCREASED from 15
        
        # INCREASED: Reviews indicate real business volume
        if lead.get("reviews_count") and lead["reviews_count"] > 50:
            opportunity_signals.append(f"Has {lead['reviews_count']} reviews - high volume business")
            opportunity_score += 35  # INCREASED from 25
        elif lead.get("reviews_count") and lead["reviews_count"] > 10:
            opportunity_signals.append(f"Has {lead['reviews_count']} reviews - active business")
            opportunity_score += 25  # INCREASED from 15
        elif lead.get("reviews_count"):
            opportunity_signals.append(f"Has {lead['reviews_count']} reviews - established business")
            opportunity_score += 15  # NEW: Even small review count is positive
        
        # INCREASED: Good rating shows quality
        if lead.get("rating") and lead["rating"] >= 4.0:
            opportunity_signals.append(f"Good rating ({lead['rating']}) - quality business")
            opportunity_score += 20  # INCREASED from 10
        elif lead.get("rating") and lead["rating"] >= 3.5:
            opportunity_signals.append(f"Decent rating ({lead['rating']}) - acceptable quality")
            opportunity_score += 10  # NEW: Even decent rating is positive
        
        # OPPORTUNITY signals (missing automation = BIG opportunity)
        # INCREASED: These are the MONEY MAKERS
        if not lead.get("has_booking_system") and lead.get("website"):
            opportunity_signals.append("NO booking system - HIGH automation opportunity")
            opportunity_score += 30  # INCREASED from 20
        
        if not lead.get("has_whatsapp") and lead.get("phone"):
            opportunity_signals.append("NO WhatsApp - HIGH messaging opportunity")
            opportunity_score += 25  # INCREASED from 15
        
        if not lead.get("has_lead_form") and lead.get("website"):
            opportunity_signals.append("NO lead form - capture opportunity")
            opportunity_score += 15  # INCREASED from 10
        
        # NEGATIVE signals (too small or unreachable)
        if not lead.get("website"):
            opportunity_signals.append("NO website - too small or inactive")
            opportunity_score -= 30
        
        if lead.get("reviews_count") and lead["reviews_count"] < 5:
            opportunity_signals.append("Very few reviews - too small")
            opportunity_score -= 20
        
        return {
            "opportunity_score": max(0, opportunity_score),
            "signals": opportunity_signals,
            "has_opportunity": opportunity_score >= 30
        }
    
    async def _llm_deep_analysis(
        self, 
        lead: Dict, 
        data_quality: Dict, 
        reachability: Dict, 
        opportunity: Dict
    ) -> Dict[str, Any]:
        """Use LLM for deep reasoning and analysis"""
        
        # Prepare context for LLM
        context = {
            "business_name": lead.get("business_name"),
            "website": lead.get("website"),
            "phone": lead.get("phone"),
            "emails": lead.get("emails", []),
            "enrichment_status": lead.get("status"),
            "has_booking_system": lead.get("has_booking_system"),
            "has_whatsapp": lead.get("has_whatsapp"),
            "has_lead_form": lead.get("has_lead_form"),
            "reviews_count": lead.get("reviews_count"),
            "rating": lead.get("rating"),
            "data_quality_score": data_quality["quality_score"],
            "data_quality_issues": data_quality["issues"],
            "reachability_score": reachability["reachability_score"],
            "reachability_issues": reachability["issues"],
            "opportunity_score": opportunity["opportunity_score"],
            "opportunity_signals": opportunity["signals"]
        }
        
        prompt = f"""You are a Supreme AI Reasoning Agent validating lead quality.

LEAD DATA:
{json.dumps(context, indent=2)}

TASK: Analyze this lead and determine if it's a REAL, HIGH-QUALITY opportunity.

CRITICAL QUESTIONS:
1. Is the data REAL or just fallback assumptions?
2. Can we actually REACH this business (website, phone, email)?
3. Is there REAL opportunity (active business + missing automation)?
4. Does the scoring make logical sense?

SCORING RULES:
- HOT (80-100): Real data + Reachable + Active business + Clear opportunity
- WARM (60-79): Some real data + Reachable + Moderate opportunity
- COLD (0-59): Fallback data OR Unreachable OR No opportunity

Provide your analysis in this format:
{{
  "verdict": "HOT|WARM|COLD",
  "confidence": 0.0-1.0,
  "reasoning": "Detailed explanation of your decision",
  "key_issues": ["issue1", "issue2"],
  "recommended_score": 0-100
}}

Be BRUTALLY HONEST. If the data is fake or the lead is unreachable, say so.
"""
        
        try:
            # LLM client is synchronous, so we call it directly (not await)
            response = self.llm.generate(
                prompt=prompt,
                temperature=0.1,  # Low temperature for consistent reasoning
                max_tokens=500
            )
            
            # Parse LLM response
            try:
                analysis = json.loads(response)
            except:
                # Fallback if LLM doesn't return valid JSON
                analysis = {
                    "verdict": "NEEDS_REVIEW",
                    "confidence": 0.5,
                    "reasoning": response,
                    "key_issues": ["LLM response parsing failed"],
                    "recommended_score": 50
                }
            
            return analysis
            
        except Exception as e:
            logger.error(f"[REASONING] LLM analysis failed: {e}")
            return {
                "verdict": "NEEDS_REVIEW",
                "confidence": 0.3,
                "reasoning": f"LLM analysis failed: {str(e)}",
                "key_issues": ["LLM unavailable"],
                "recommended_score": 50
            }
    
    def _make_final_decision(
        self,
        lead: Dict,
        data_quality: Dict,
        reachability: Dict,
        opportunity: Dict,
        llm_analysis: Dict
    ) -> ReasoningResult:
        """Make the final decision based on all analysis"""
        
        all_issues = []
        all_issues.extend(data_quality["issues"])
        all_issues.extend(reachability["issues"])
        all_issues.extend(llm_analysis.get("key_issues", []))
        
        # Calculate composite score
        composite_score = (
            data_quality["quality_score"] * 0.3 +
            reachability["reachability_score"] * 0.3 +
            opportunity["opportunity_score"] * 0.4
        )
        
        # Use LLM recommendation if available
        llm_score = llm_analysis.get("recommended_score", composite_score)
        final_score = (composite_score * 0.5 + llm_score * 0.5)
        
        # Determine verdict (REALISTIC for Indian healthcare)
        # Most businesses will score 40-70, not 80-100
        # We need to be AGGRESSIVE to find opportunities
        if final_score >= 55:  # LOWERED from 70 - Good opportunity
            verdict = "ACCEPT"
            tier = "HOT"
        elif final_score >= 35:  # LOWERED from 50 - Decent opportunity
            verdict = "ACCEPT"
            tier = "WARM"
        elif final_score >= 20:  # LOWERED from 30 - Marginal
            verdict = "NEEDS_REVIEW"
            tier = "COLD"
        else:
            verdict = "REJECT"
            tier = "DISQUALIFIED"
        
        # Build reasoning
        reasoning_parts = [
            f"Data Quality: {data_quality['quality_score']}/100",
            f"Reachability: {reachability['reachability_score']}/100",
            f"Opportunity: {opportunity['opportunity_score']}/100",
            f"Composite Score: {final_score:.1f}/100",
            f"LLM Analysis: {llm_analysis.get('reasoning', 'N/A')}"
        ]
        
        # Corrections to apply
        corrections = {
            "leak_score": int(final_score),
            "priority": tier,
            "data_quality_score": data_quality["quality_score"],
            "reachability_score": reachability["reachability_score"],
            "opportunity_score": opportunity["opportunity_score"],
            "reasoning_verdict": verdict,
            "ai_reasoning": llm_analysis.get("reasoning", ""),
            "validation_issues": all_issues
        }
        
        return ReasoningResult(
            is_valid=verdict == "ACCEPT",
            confidence=llm_analysis.get("confidence", 0.7),
            reasoning="\n".join(reasoning_parts),
            issues_found=all_issues,
            corrections=corrections,
            final_verdict=verdict
        )
    
    def explain_decision(self, result: ReasoningResult) -> str:
        """Generate human-readable explanation of the decision"""
        
        explanation = f"""
╔══════════════════════════════════════════════════════════════╗
║              AI REASONING AGENT - DECISION REPORT            ║
╚══════════════════════════════════════════════════════════════╝

VERDICT: {result.final_verdict}
CONFIDENCE: {result.confidence:.1%}

REASONING:
{result.reasoning}

ISSUES FOUND ({len(result.issues_found)}):
"""
        for i, issue in enumerate(result.issues_found, 1):
            explanation += f"  {i}. {issue}\n"
        
        explanation += f"""
CORRECTIONS APPLIED:
  - Final Score: {result.corrections.get('leak_score')}/100
  - Priority: {result.corrections.get('priority')}
  - Data Quality: {result.corrections.get('data_quality_score')}/100
  - Reachability: {result.corrections.get('reachability_score')}/100
  - Opportunity: {result.corrections.get('opportunity_score')}/100

AI ANALYSIS:
{result.corrections.get('ai_reasoning', 'N/A')}

═══════════════════════════════════════════════════════════════
"""
        return explanation
