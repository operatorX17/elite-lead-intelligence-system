import { auth } from "@/app/(auth)/auth";
import { ZRAI_BACKEND_URL } from "@/lib/zrai/constants";
import { authError, backendError, notFoundError } from "@/lib/zrai/errors";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ leadId: string }> }
): Promise<Response> {
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
