/**
 * ZRAI Lead OS - Scoring Endpoint
 *
 * POST /api/zrai/score
 * Scores leads based on intent, fit, and engagement via the ZRAI Scoring Agent.
 */

import { z } from "zod";
import { auth } from "@/app/(auth)/auth";
import { ZRAI_BACKEND_URL } from "@/lib/zrai/constants";
import {
  authError,
  backendError,
  validationError,
  ZRAIAPIError,
} from "@/lib/zrai/errors";
import type { ScoringResult } from "@/lib/zrai/types";

// ============================================================================
// Request Schema
// ============================================================================

const scoreRequestSchema = z.object({
  niche: z.string().optional(),
  geo: z.string().optional(),
  min_score: z.number().min(0).max(100).optional(),
  lead_ids: z.array(z.string().uuid()).optional(),
});

type ScoreRequest = z.infer<typeof scoreRequestSchema>;

// ============================================================================
// Response Types
// ============================================================================

type ScoreResponse = {
  success: boolean;
  data?: {
    results: ScoringResult[];
    count: number;
  };
  error?: {
    code: string;
    message: string;
  };
};

// ============================================================================
// Route Handler
// ============================================================================

export async function POST(request: Request): Promise<Response> {
  try {
    // Authenticate
    const session = await auth();
    if (!session?.user) {
      return authError("score").toResponse();
    }

    // Parse and validate request
    let body: ScoreRequest;
    try {
      const json = await request.json();
      body = scoreRequestSchema.parse(json);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return validationError("score", {
          errors: error.errors.map((e) => ({
            field: e.path.join("."),
            message: e.message,
          })),
        }).toResponse();
      }
      return validationError("score", {
        message: "Invalid JSON body",
      }).toResponse();
    }

    // Call ZRAI backend
    const backendResponse = await fetch(`${ZRAI_BACKEND_URL}/api/v1/score`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-ID": session.user.id,
      },
      body: JSON.stringify(body),
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));

      if (backendResponse.status === 429) {
        return new ZRAIAPIError(
          "rate_limit",
          "score",
          errorData.message || "Rate limit exceeded",
          undefined,
          errorData.retry_after
        ).toResponse();
      }

      if (backendResponse.status === 503) {
        return new ZRAIAPIError(
          "circuit_open",
          "score",
          errorData.message || "Scoring agent is temporarily unavailable"
        ).toResponse();
      }

      return backendError(
        "score",
        errorData.detail || errorData.message
      ).toResponse();
    }

    const data = await backendResponse.json();
    const backendResults = data.results || data.scored_leads || [];
    const results: ScoringResult[] = backendResults.map((result: any) => {
      const breakdown =
        result.breakdown?.score_breakdown || result.breakdown || {};
      const totalScore =
        result.score ?? result.lead?.score ?? breakdown.total_score ?? 0;

      return {
        lead_id: result.lead_id,
        lead: result.lead,
        score_breakdown: {
          intent_score: breakdown.intent ?? breakdown.intent_score ?? 0,
          fit_score: breakdown.contact_quality ?? breakdown.fit_score ?? 0,
          engagement_score: breakdown.leak ?? breakdown.engagement_score ?? 0,
          recency_score: breakdown.reactivation ?? breakdown.recency_score ?? 0,
          total_score: totalScore,
        },
        disqualified: result.disqualified ?? false,
        disqualification_reason: result.disqualification_reason,
        scored_at: new Date().toISOString(),
      };
    });

    const response: ScoreResponse = {
      success: true,
      data: {
        results,
        count: data.count || results.length,
      },
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error("[ZRAI:score] Error:", error);
    return backendError(
      "score",
      error instanceof Error ? error.message : "Unknown error"
    ).toResponse();
  }
}
