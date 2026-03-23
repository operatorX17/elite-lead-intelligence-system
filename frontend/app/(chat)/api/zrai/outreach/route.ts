/**
 * ZRAI Lead OS - Outreach Endpoint
 *
 * POST /api/zrai/outreach
 * Drafts and sends outreach messages via the ZRAI Outreach Agent.
 */

import { z } from "zod";
import { auth } from "@/app/(auth)/auth";
import { ZRAI_BACKEND_URL } from "@/lib/zrai/constants";
import {
  authError,
  backendError,
  doNotContactError,
  notFoundError,
  validationError,
  ZRAIAPIError,
} from "@/lib/zrai/errors";
import { toOutreachMessage } from "@/lib/zrai/transformers";
import type { OutreachMessage } from "@/lib/zrai/types";

// ============================================================================
// Request Schema
// ============================================================================

const outreachRequestSchema = z.object({
  lead_id: z.string().uuid("Invalid lead ID format"),
  channel: z.enum(["email", "linkedin", "sms"]),
  action: z.enum(["draft", "send"]),
  message_id: z.string().uuid().optional(), // Required for send action
  message: z.string().optional(), // Optional override for send action
});

type OutreachRequest = z.infer<typeof outreachRequestSchema>;

// ============================================================================
// Response Types
// ============================================================================

type OutreachResponse = {
  success: boolean;
  data?: {
    message: OutreachMessage;
    sent?: boolean;
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
      return authError("outreach").toResponse();
    }

    // Parse and validate request
    let body: OutreachRequest;
    try {
      const json = await request.json();
      body = outreachRequestSchema.parse(json);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return validationError("outreach", {
          errors: error.errors.map((e) => ({
            field: e.path.join("."),
            message: e.message,
          })),
        }).toResponse();
      }
      return validationError("outreach", {
        message: "Invalid JSON body",
      }).toResponse();
    }

    // Validate send action has message_id
    if (body.action === "send" && !body.message_id) {
      return validationError("outreach", {
        message: "message_id is required for send action",
      }).toResponse();
    }

    // Call ZRAI backend
    const backendResponse = await fetch(`${ZRAI_BACKEND_URL}/api/v1/outreach`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-ID": session.user.id,
      },
      body: JSON.stringify(body),
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));

      if (backendResponse.status === 404) {
        return notFoundError("outreach", "Lead").toResponse();
      }

      if (backendResponse.status === 429) {
        return new ZRAIAPIError(
          "rate_limit",
          "outreach",
          errorData.message || "Rate limit exceeded for outreach",
          undefined,
          errorData.retry_after
        ).toResponse();
      }

      if (backendResponse.status === 402) {
        return new ZRAIAPIError(
          "budget_exceeded",
          "outreach",
          errorData.message || "Budget exceeded for outreach"
        ).toResponse();
      }

      if (backendResponse.status === 503) {
        return new ZRAIAPIError(
          "circuit_open",
          "outreach",
          errorData.message || "Outreach agent is temporarily unavailable"
        ).toResponse();
      }

      // Handle do-not-contact
      if (errorData.code === "do_not_contact") {
        return doNotContactError("outreach", body.lead_id).toResponse();
      }

      // Handle governance violations
      if (errorData.code === "governance_violation") {
        return new ZRAIAPIError(
          "governance_violation",
          "outreach",
          errorData.message || "This outreach violates governance rules"
        ).toResponse();
      }

      return backendError(
        "outreach",
        errorData.detail || errorData.message
      ).toResponse();
    }

    const data = await backendResponse.json();
    const backendMessages = Array.isArray(data.outreach) ? data.outreach : [];
    const primaryMessage = backendMessages[0]
      ? toOutreachMessage(backendMessages[0], body.channel)
      : null;

    if (!primaryMessage) {
      return backendError(
        "outreach",
        "No outreach draft was generated."
      ).toResponse();
    }

    const response: OutreachResponse = {
      success: true,
      data: {
        message: primaryMessage,
        sent:
          body.action === "send" ? primaryMessage.status === "sent" : undefined,
      },
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error("[ZRAI:outreach] Error:", error);
    return backendError(
      "outreach",
      error instanceof Error ? error.message : "Unknown error"
    ).toResponse();
  }
}
