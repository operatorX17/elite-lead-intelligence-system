/**
 * ZRAI Lead OS - Pipeline Run Endpoint
 *
 * POST /api/zrai/run - Trigger pipeline runs
 * GET /api/zrai/run/:id - Get run status
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
import type { PipelineRun } from "@/lib/zrai/types";

// ============================================================================
// Request Schema
// ============================================================================

const runRequestSchema = z.object({
  mode: z.enum(["full", "dry_run", "replay", "resume"]),
  config: z.record(z.unknown()).optional(),
  run_id: z.string().uuid().optional(), // Required for replay/resume
  limit: z.number().min(1).max(1000).optional(), // For dry_run
});

type RunRequest = z.infer<typeof runRequestSchema>;

// ============================================================================
// Response Types
// ============================================================================

type RunResponse = {
  success: boolean;
  data?: PipelineRun;
  error?: {
    code: string;
    message: string;
  };
};

function normalizePipelineRun(data: any): PipelineRun {
  return {
    id: data.id || data.run_id || "",
    mode: data.mode || "dry_run",
    status: data.status || "completed",
    config_snapshot: data.config_snapshot || data.config || {},
    started_at: data.started_at || new Date().toISOString(),
    completed_at: data.completed_at
      ? data.completed_at
      : data.status === "running"
        ? undefined
        : new Date().toISOString(),
    stats: {
      leads_processed: data.processed || data.stats?.leads_processed || 0,
      leads_succeeded: data.stats?.leads_succeeded || data.processed || 0,
      leads_failed: data.stats?.leads_failed || 0,
      errors: data.stats?.errors || [],
    },
  };
}

// ============================================================================
// Route Handlers
// ============================================================================

export async function POST(request: Request): Promise<Response> {
  try {
    // Authenticate
    const session = await auth();
    if (!session?.user) {
      return authError("run").toResponse();
    }

    // Parse and validate request
    let body: RunRequest;
    try {
      const json = await request.json();
      body = runRequestSchema.parse(json);
    } catch (error) {
      if (error instanceof z.ZodError) {
        return validationError("run", {
          errors: error.errors.map((e) => ({
            field: e.path.join("."),
            message: e.message,
          })),
        }).toResponse();
      }
      return validationError("run", {
        message: "Invalid JSON body",
      }).toResponse();
    }

    // Validate replay/resume has run_id
    if ((body.mode === "replay" || body.mode === "resume") && !body.run_id) {
      return validationError("run", {
        message: `run_id is required for ${body.mode} mode`,
      }).toResponse();
    }

    // Call ZRAI backend
    const backendResponse = await fetch(`${ZRAI_BACKEND_URL}/api/v1/run`, {
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
        return notFoundError("run", "Pipeline run").toResponse();
      }

      if (backendResponse.status === 429) {
        return new ZRAIAPIError(
          "rate_limit",
          "run",
          errorData.message || "Rate limit exceeded",
          undefined,
          errorData.retry_after
        ).toResponse();
      }

      if (backendResponse.status === 402) {
        return new ZRAIAPIError(
          "budget_exceeded",
          "run",
          errorData.message || "Budget exceeded for pipeline runs"
        ).toResponse();
      }

      return backendError(
        "run",
        errorData.detail || errorData.message
      ).toResponse();
    }

    const data = await backendResponse.json();

    const response: RunResponse = {
      success: true,
      data: normalizePipelineRun(data.run || data),
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error("[ZRAI:run] Error:", error);
    return backendError(
      "run",
      error instanceof Error ? error.message : "Unknown error"
    ).toResponse();
  }
}

export async function GET(request: Request): Promise<Response> {
  try {
    // Authenticate
    const session = await auth();
    if (!session?.user) {
      return authError("run").toResponse();
    }

    // Get run ID from URL
    const url = new URL(request.url);
    const runId = url.pathname.split("/").pop();

    if (!runId || runId === "run") {
      // List recent runs
      const backendResponse = await fetch(`${ZRAI_BACKEND_URL}/api/v1/run`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": session.user.id,
        },
      });

      if (!backendResponse.ok) {
        const errorData = await backendResponse.json().catch(() => ({}));
        return backendError(
          "run",
          errorData.detail || errorData.message
        ).toResponse();
      }

      const data = await backendResponse.json();
      return Response.json(
        { success: true, data: data.runs || [] },
        { status: 200 }
      );
    }

    // Get specific run
    const backendResponse = await fetch(
      `${ZRAI_BACKEND_URL}/api/v1/run/${runId}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": session.user.id,
        },
      }
    );

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));

      if (backendResponse.status === 404) {
        return notFoundError("run", "Pipeline run").toResponse();
      }

      return backendError(
        "run",
        errorData.detail || errorData.message
      ).toResponse();
    }

    const data = await backendResponse.json();

    const response: RunResponse = {
      success: true,
      data: normalizePipelineRun(data.run || data),
    };

    return Response.json(response, { status: 200 });
  } catch (error) {
    console.error("[ZRAI:run] Error:", error);
    return backendError(
      "run",
      error instanceof Error ? error.message : "Unknown error"
    ).toResponse();
  }
}
