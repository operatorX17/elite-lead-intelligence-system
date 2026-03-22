import { NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";
import { signIn } from "@/app/(auth)/auth";
import {
  isDevelopmentEnvironment,
  ZRAI_GUEST_ID_COOKIE,
} from "@/lib/constants";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const redirectUrl = searchParams.get("redirectUrl") || "/";

  const token = await getToken({
    req: request,
    secret: process.env.AUTH_SECRET,
    secureCookie: !isDevelopmentEnvironment,
  });

  if (token) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  const requestUrl = new URL(request.url);
  const existingGuestId = requestUrl.searchParams.get("guestId");
  const guestCookie = request.headers
    .get("cookie")
    ?.split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${ZRAI_GUEST_ID_COOKIE}=`))
    ?.split("=")[1];

  const stableGuestId = guestCookie ?? existingGuestId ?? crypto.randomUUID();

  if (!guestCookie) {
    const redirectResponse = NextResponse.redirect(
      new URL(
        `/api/auth/guest?redirectUrl=${encodeURIComponent(
          redirectUrl
        )}&guestId=${stableGuestId}`,
        request.url
      )
    );

    redirectResponse.cookies.set(ZRAI_GUEST_ID_COOKIE, stableGuestId, {
      httpOnly: true,
      sameSite: "lax",
      secure: !isDevelopmentEnvironment,
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
    });

    return redirectResponse;
  }

  return signIn("guest", {
    redirect: true,
    redirectTo: redirectUrl,
    guestId: stableGuestId,
  });
}
