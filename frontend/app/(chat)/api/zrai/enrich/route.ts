/**
 * ZRAI Lead OS - Enrichment Endpoint
 *
 * POST /api/zrai/enrich
 * Enriches a lead with additional data via the ZRAI Enrichment Agent.
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
import type { EnrichmentData, Lead } from "@/lib/zrai/types";

// ============================================================================
// Request Schema
// ============================================================================

const enrichRequestSchema = z.object({
  lead_id: z.string().uuid("Invalid lead ID format"),
});

type EnrichRequest = z.infer<typeof enrichRequestSchema>;

// ============================================================================
// Response Types
// ============================================================================

type EnrichResponse = {
  success: boolean;
  data?: {
    lead: Lead;
    enrichment: EnrichmentData;
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
      return authError("enrich").toResponse();
    }

    // Parse and validate request
    let body: EnrichRequest;
    try {
      const json = await request.json();
      body = enrichRequestSchema.parse(json);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return validationError("enrich", {
          errors: error.errors.map((e) => ({
            field: e.path.join("."),
            message: e.message,
          })),
        }).toResponse();
      }
      return validationError("enrich", {
        message: "Invalid JSON body",
      }).toResponse();
    }

    // Call ZRAI backend
    const backendResponse = await fetch(`${ZRAI_BACKEND_URL}/api/v1/enrich`, {
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
        return notFoundError("enrich", "Lead").toResponse();
      }

      if (backendResponse.status === 429) {
        return new ZRAIAPIError(
          "rate_limit",
          "enrich",
          errorData.message || "Rate limit exceeded",
          undefined,
          errorData.retry_after
        ).toResponse();
      }

      if (backendResponse.status === 402) {
        return new ZRAIAPIError(
          "budget_exceeded",
          "enrich",
          errorData.message || "Budget exceeded for enrichment"
        ).toResponse();
      }

      if (backendResponse.status === 503) {
        return new ZRAIAPIError(
          "circuit_open",
          "enrich",
          errorData.message || "Enrichment agent is temporarily unavailable"
        ).toResponse();
      }

      return backendError(
        "enrich",
        errorData.detail || errorData.message
      ).toResponse();
    }

    const data = await backendResponse.json();

    const response: EnrichResponse = {
      success: true,
      data: {
        lead: data.lead,
        enrichment: data.enrichment,
      },
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error("[ZRAI:enrich] Error:", error);
    return backendError(
      "enrich",
      error instanceof Error ? error.message : "Unknown error"
    ).toResponse();
  }
}
