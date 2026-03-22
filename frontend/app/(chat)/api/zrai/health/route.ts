/**
 * ZRAI Lead OS - Health Endpoint
 *
 * GET /api/zrai/health
 * Proxies backend health so the chat landing UI can show system readiness.
 */

import { auth } from "@/app/(auth)/auth";
import { ZRAI_BACKEND_URL } from "@/lib/zrai/constants";
import { authError, backendError } from "@/lib/zrai/errors";

type HealthResponse = {
  success: boolean;
  data?: {
    status: string;
    service: string;
    agents: Record<string, boolean>;
  };
  error?: {
    code: string;
    message: string;
  };
};

export async function GET(): Promise<Response> {
  try {
    const session = await auth();

    if (!session?.user) {
      return authError("health").toResponse();
    }

    const backendResponse = await fetch(`${ZRAI_BACKEND_URL}/health`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-User-ID": session.user.id,
      },
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));
      return backendError("health", errorData.message).toResponse();
    }

    const data = await backendResponse.json();

    const response: HealthResponse = {
      success: true,
      data: {
        status: data.status || "unknown",
        service: data.service || "zrai-lead-os",
        agents: data.agents || {},
      },
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error("[ZRAI:health] Error:", error);
    return backendError(
      "health",
      error instanceof Error ? error.message : "Unknown error"
    ).toResponse();
  }
}
