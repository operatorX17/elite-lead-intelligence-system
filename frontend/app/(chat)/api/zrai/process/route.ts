import { z } from "zod";
import { auth } from "@/app/(auth)/auth";
import { ZRAI_BACKEND_URL } from "@/lib/zrai/constants";
import { authError, backendError, validationError, ZRAIAPIError } from "@/lib/zrai/errors";

const processRequestSchema = z.object({
  lead_ids: z.array(z.string().uuid()).min(1, "At least one lead is required"),
  include_outreach: z.boolean().optional().default(true),
});

export async function POST(request: Request): Promise<Response> {
  try {
    const session = await auth();
    if (!session?.user) {
      return authError("run").toResponse();
    }

    let body: z.infer<typeof processRequestSchema>;
    try {
      body = processRequestSchema.parse(await request.json());
    } catch (error) {
      if (error instanceof z.ZodError) {
        return validationError("run", {
          errors: error.errors.map((e) => ({
            field: e.path.join("."),
            message: e.message,
          })),
        }).toResponse();
      }
      return validationError("run", { message: "Invalid JSON body" }).toResponse();
    }

    const backendResponse = await fetch(`${ZRAI_BACKEND_URL}/api/v1/process-leads`, {
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
          "run",
          errorData.message || "Rate limit exceeded",
          undefined,
          errorData.retry_after
        ).toResponse();
      }
      if (backendResponse.status === 503) {
        return new ZRAIAPIError(
          "circuit_open",
          "run",
          errorData.message || "Process pipeline is temporarily unavailable"
        ).toResponse();
      }

      return backendError("run", errorData.detail || errorData.message).toResponse();
    }

    const data = await backendResponse.json();
    return Response.json(data, { status: 200 });
  } catch (error) {
    console.error("[ZRAI:process] Error:", error);
    return backendError(
      "run",
      error instanceof Error ? error.message : "Unknown error"
    ).toResponse();
  }
}
