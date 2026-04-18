import { auth } from "@/app/(auth)/auth";
import { ZRAI_BACKEND_URL } from "@/lib/zrai/constants";
import { authError, backendError, notFoundError } from "@/lib/zrai/errors";
import { connection } from "next/server";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ leadId: string }> }
): Promise<Response> {
  await connection();
  try {
    const session = await auth();
    if (!session?.user) {
      return authError("leads").toResponse();
    }

    const { leadId } = await params;
    const backendResponse = await fetch(`${ZRAI_BACKEND_URL}/api/v1/leads/${leadId}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-User-ID": session.user.id,
      },
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));
      if (backendResponse.status === 404) {
        return notFoundError("leads", "Lead").toResponse();
      }
      return backendError("leads", errorData.detail || errorData.message).toResponse();
    }

    const data = await backendResponse.json();
    return Response.json(data, { status: 200 });
  } catch (error) {
    console.error("[ZRAI:lead] Error:", error);
    return backendError(
      "leads",
      error instanceof Error ? error.message : "Unknown error"
    ).toResponse();
  }
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ leadId: string }> }
): Promise<Response> {
  await connection();
  try {
    const session = await auth();
    if (!session?.user) {
      return authError("leads").toResponse();
    }

    const { leadId } = await params;
    const body = (await request.json().catch(() => ({}))) as {
      include_outreach?: boolean;
      async?: boolean;
      force_refresh?: boolean;
    };
    const includeOutreach = Boolean(body.include_outreach);
    const useAsync = body.async !== false;
    const backendPath = useAsync ? "/api/v1/analyze-lead-async" : "/api/v1/analyze-lead";

    const backendResponse = await fetch(`${ZRAI_BACKEND_URL}${backendPath}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-ID": session.user.id,
      },
      body: JSON.stringify({
        lead_id: leadId,
        include_outreach: includeOutreach,
        force_refresh: body.force_refresh ?? true,
      }),
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));
      if (backendResponse.status === 404) {
        return notFoundError("leads", "Lead").toResponse();
      }
      return backendError("leads", errorData.detail || errorData.message).toResponse();
    }

    const data = await backendResponse.json();
    return Response.json(data, { status: backendResponse.status || 200 });
  } catch (error) {
    console.error("[ZRAI:lead-refresh] Error:", error);
    return backendError(
      "leads",
      error instanceof Error ? error.message : "Unknown error"
    ).toResponse();
  }
}
