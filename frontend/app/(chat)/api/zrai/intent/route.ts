/**
 * ZRAI Lead OS - Intent Analysis Endpoint
 *
 * POST /api/zrai/intent
 * Analyzes intent signals for a lead via the ZRAI Intent Agent.
 */

import { z } from "zod";
import { auth } from "@/app/(auth)/auth";
import { ZRAI_BACKEND_URL } from "@/lib/zrai/constants";
import {
  authError,
  backendError,
  notFoundError,
  validationError,
  ZRAIAPIError,
} from "@/lib/zrai/errors";
import type { IntentSignal, Lead } from "@/lib/zrai/types";

// ============================================================================
// Request Schema
// ============================================================================

const intentRequestSchema = z.object({
  lead_id: z.string().uuid("Invalid lead ID format"),
});

type IntentRequest = z.infer<typeof intentRequestSchema>;

// ============================================================================
// Response Types
// ============================================================================

type IntentResponse = {
  success: boolean;
  data?: {
    lead: Lead;
    intent_signals: IntentSignal[];
    revenue_leak_score: number;
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
      return authError("intent").toResponse();
    }

    // Parse and validate request
    let body: IntentRequest;
    try {
      const json = await request.json();
      body = intentRequestSchema.parse(json);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return validationError("intent", {
          errors: error.errors.map((e) => ({
            field: e.path.join("."),
            message: e.message,
          })),
        }).toResponse();
      }
      return validationError("intent", {
        message: "Invalid JSON body",
      }).toResponse();
    }

    // Call ZRAI backend
    const backendResponse = await fetch(`${ZRAI_BACKEND_URL}/api/v1/intent`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-ID": session.user.id,
      },
      body: JSON.stringify({
        lead_id: body.lead_id,
      }),
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));

      if (backendResponse.status === 404) {
        return notFoundError("intent", "Lead").toResponse();
      }

      if (backendResponse.status === 429) {
        return new ZRAIAPIError(
          "rate_limit",
          "intent",
          errorData.message || "Rate limit exceeded",
          undefined,
          errorData.retry_after
        ).toResponse();
      }

      if (backendResponse.status === 503) {
        return new ZRAIAPIError(
          "circuit_open",
          "intent",
          errorData.message || "Intent agent is temporarily unavailable"
        ).toResponse();
      }

      return backendError(
        "intent",
        errorData.detail || errorData.message
      ).toResponse();
    }

    const data = await backendResponse.json();

    const response: IntentResponse = {
      success: true,
      data: {
        lead: data.lead,
        intent_signals: data.lead?.intent_signals || [],
        revenue_leak_score: data.intent?.leak_score || 0,
      },
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error("[ZRAI:intent] Error:", error);
    return backendError(
      "intent",
      error instanceof Error ? error.message : "Unknown error"
    ).toResponse();
  }
}
