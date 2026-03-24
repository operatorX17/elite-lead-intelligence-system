/**
 * ZRAI Lead OS - Conversation Endpoint
 *
 * POST /api/zrai/conversation
 * Handles lead conversations via the ZRAI Conversation Agent.
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
import { toConversation } from "@/lib/zrai/transformers";
import type { Conversation } from "@/lib/zrai/types";









// ============================================================================
// Request Schema
// ============================================================================

const conversationRequestSchema = z.object({
  lead_id: z.string().uuid("Invalid lead ID format"),
  message: z.string().min(1, "Message is required"),
  channel: z.enum(["email", "linkedin", "sms", "whatsapp", "instagram", "website_chat"]).optional(),
});

type ConversationRequest = z.infer<typeof conversationRequestSchema>;

// ============================================================================
// Escalation Request Schema
// ============================================================================

const escalationRequestSchema = z.object({
  lead_id: z.string().uuid("Invalid lead ID format"),
  reason: z.string().min(1, "Reason is required"),
  assignee: z.string().optional(),
});

type EscalationRequest = z.infer<typeof escalationRequestSchema>;

// ============================================================================
// Response Types
// ============================================================================

type ConversationResponse = {
  success: boolean;
  data?: {
    conversation: Conversation;
    ai_response: string;
    needs_escalation: boolean;
    escalation_reason?: string;
  };
  error?: {
    code: string;
    message: string;
  };
};

type EscalationResponse = {
  success: boolean;
  data?: {
    conversation: Conversation;
    escalated: boolean;
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
      return authError("conversation").toResponse();
    }

    // Check if this is an escalation request
    const url = new URL(request.url);
    const isEscalation = url.pathname.endsWith("/escalate");

    if (isEscalation) {
      return handleEscalation(request, session.user.id);
    }

    // Parse and validate request
    let body: ConversationRequest;
    try {
      const json = await request.json();
      body = conversationRequestSchema.parse(json);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return validationError("conversation", {
          errors: error.errors.map((e) => ({
            field: e.path.join("."),
            message: e.message,
          })),
        }).toResponse();
      }
      return validationError("conversation", {
        message: "Invalid JSON body",
      }).toResponse();
    }

    // Call ZRAI backend
    const backendResponse = await fetch(
      `${ZRAI_BACKEND_URL}/api/v1/conversation`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": session.user.id,
        },
        body: JSON.stringify(body),
      }
    );

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));

      if (backendResponse.status === 404) {
        return notFoundError("conversation", "Lead").toResponse();
      }

      if (backendResponse.status === 429) {
        return new ZRAIAPIError(
          "rate_limit",
          "conversation",
          errorData.message || "Rate limit exceeded",
          undefined,
          errorData.retry_after
        ).toResponse();
      }

      if (backendResponse.status === 503) {
        return new ZRAIAPIError(
          "circuit_open",
          "conversation",
          errorData.message || "Conversation agent is temporarily unavailable"
        ).toResponse();
      }

      return backendError(
        "conversation",
        errorData.detail || errorData.message
      ).toResponse();
    }

    const data = await backendResponse.json();
    const conversation = toConversation(
      data.conversation || {},
      body.channel || "email"
    );
    const lastAiMessage = [...conversation.messages]
      .reverse()
      .find((message) => message.sender === "ai");

    const response: ConversationResponse = {
      success: true,
      data: {
        conversation,
        ai_response:
          lastAiMessage?.content ||
          (typeof data.response === "string"
            ? data.response
            : data.response?.message) ||
          data.ai_response ||
          "",
        needs_escalation: data.needs_escalation || false,
        escalation_reason: data.escalation_reason,
      },
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error("[ZRAI:conversation] Error:", error);
    return backendError(
      "conversation",
      error instanceof Error ? error.message : "Unknown error"
    ).toResponse();
  }
}

// ============================================================================
// Escalation Handler
// ============================================================================

async function handleEscalation(
  request: Request,
  userId: string
): Promise<Response> {
  try {
    // Parse and validate request
    let body: EscalationRequest;
    try {
      const json = await request.json();
      body = escalationRequestSchema.parse(json);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return validationError("conversation", {
          errors: error.errors.map((e) => ({
            field: e.path.join("."),
            message: e.message,
          })),
        }).toResponse();
      }
      return validationError("conversation", {
        message: "Invalid JSON body",
      }).toResponse();
    }

    // Call ZRAI backend
    const backendResponse = await fetch(
      `${ZRAI_BACKEND_URL}/api/v1/conversation/escalate`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": userId,
        },
        body: JSON.stringify(body),
      }
    );

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));

      if (backendResponse.status === 404) {
        return notFoundError(
          "conversation",
          "Lead or conversation"
        ).toResponse();
      }

      return backendError("conversation", errorData.message).toResponse();
    }

    const data = await backendResponse.json();

    const response: EscalationResponse = {
      success: true,
      data: {
        conversation: data.conversation,
        escalated: data.escalated || true,
      },
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error("[ZRAI:conversation:escalate] Error:", error);
    return backendError(
      "conversation",
      error instanceof Error ? error.message : "Unknown error"
    ).toResponse();
  }
}

