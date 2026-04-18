import { z } from "zod";
import { auth } from "@/app/(auth)/auth";
import { ZRAI_BACKEND_URL } from "@/lib/zrai/constants";
import { authError, backendError, notFoundError, validationError, ZRAIAPIError } from "@/lib/zrai/errors";
import { persistImportableLead } from "@/lib/zrai/import-bridge";









const importableLeadSchema = z.object({
  id: z.string().min(1).optional(),
  company_name: z.string().min(1, "Company name is required for preview leads"),
  domain: z.string().min(1, "Domain is required for preview leads"),
  niche: z.string().optional(),
  verified_fit: z.string().optional(),
  geo: z.string().optional(),
  source: z.string().optional(),
  source_label: z.string().optional(),
  contacts: z
    .array(
      z.object({
        name: z.string().optional(),
        email: z.string().optional(),
        phone: z.string().optional(),
        linkedin_url: z.string().optional(),
        title: z.string().optional(),
      })
    )
    .optional(),
});

const analyzeRequestSchema = z.object({
  lead_id: z.string().min(1, "Lead id is required"),
  include_outreach: z.boolean().optional().default(true),
  force_refresh: z.boolean().optional().default(false),
  lead: importableLeadSchema.optional(),
});

function isUuid(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

async function materializeLeadId(
  body: z.infer<typeof analyzeRequestSchema>,
  _userId: string
) {
  if (isUuid(body.lead_id)) {
    return body.lead_id;
  }

  if (!body.lead) {
    throw validationError("run", {
      errors: [
        {
          field: "lead_id",
          message: "Invalid lead ID format",
        },
      ],
    });
  }

  const importedLead = await persistImportableLead(body.lead);

  if (!importedLead?.id || !isUuid(importedLead.id)) {
    throw backendError("run", "Failed to resolve preview lead into a persisted lead");
  }

  return importedLead.id as string;
}

export async function POST(request: Request): Promise<Response> {
  try {
    const session = await auth();
    if (!session?.user) {
      return authError("run").toResponse();
    }

    let body: z.infer<typeof analyzeRequestSchema>;
    try {
      body = analyzeRequestSchema.parse(await request.json());
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

    let leadId: string;
    try {
      leadId = await materializeLeadId(body, session.user.id);
    } catch (error) {
      if (
        typeof error === "object" &&
        error !== null &&
        "toResponse" in error &&
        typeof (error as { toResponse?: unknown }).toResponse === "function"
      ) {
        return (error as { toResponse: () => Response }).toResponse();
      }
      throw error;
    }

    const backendPath = body.include_outreach ? "/api/v1/analyze-lead-async" : "/api/v1/analyze-lead";

    const backendResponse = await fetch(`${ZRAI_BACKEND_URL}${backendPath}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-ID": session.user.id,
      },
      body: JSON.stringify({
        lead_id: leadId,
        include_outreach: body.include_outreach,
        force_refresh: body.force_refresh,
      }),
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));

      if (backendResponse.status === 404) {
        return notFoundError("run", "Lead").toResponse();
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
      if (backendResponse.status === 503) {
        return new ZRAIAPIError(
          "circuit_open",
          "run",
          errorData.message || "Analyze pipeline is temporarily unavailable"
        ).toResponse();
      }

      return backendError("run", errorData.detail || errorData.message).toResponse();
    }

    const data = await backendResponse.json();
    return Response.json(data, { status: backendResponse.status || 200 });
  } catch (error) {
    console.error("[ZRAI:analyze] Error:", error);
    return backendError(
      "run",
      error instanceof Error ? error.message : "Unknown error"
    ).toResponse();
  }
}

