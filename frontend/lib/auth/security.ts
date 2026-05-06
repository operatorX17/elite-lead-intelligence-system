const AUTH_WINDOW_MS = 15 * 60 * 1000;
const AUTH_LOCK_MS = 15 * 60 * 1000;
const AUTH_MAX_FAILURES = 5;

type AuthAttemptState = {
  failures: number;
  windowStartedAt: number;
  lockUntil: number;
};

const authAttemptState = new Map<string, AuthAttemptState>();

export function normalizeAuthEmail(value: unknown) {
  return String(value ?? "").trim().toLowerCase();
}

function getForwardedIp(value: string | null) {
  return String(value || "")
    .split(",")[0]
    ?.trim()
    ?.slice(0, 128) || "unknown";
}

export function getRequestIp(request: Request | undefined) {
  if (!request) {
    return "unknown";
  }

  return (
    getForwardedIp(request.headers.get("x-forwarded-for")) ||
    String(request.headers.get("x-real-ip") || "").trim() ||
    "unknown"
  );
}

function getAuthRateLimitKeys(email: string, request: Request | undefined) {
  const normalizedEmail = normalizeAuthEmail(email) || "unknown";
  const ip = getRequestIp(request);
  return [`email:${normalizedEmail}`, `ip:${ip}`, `combo:${normalizedEmail}:${ip}`];
}

function getFreshState(key: string, now: number) {
  const current = authAttemptState.get(key);
  if (!current) {
    return {
      failures: 0,
      windowStartedAt: now,
      lockUntil: 0,
    };
  }

  if (current.lockUntil > now) {
    return current;
  }

  if (now - current.windowStartedAt > AUTH_WINDOW_MS) {
    return {
      failures: 0,
      windowStartedAt: now,
      lockUntil: 0,
    };
  }

  return current;
}

export function isAuthRateLimited(email: string, request: Request | undefined) {
  const now = Date.now();
  return getAuthRateLimitKeys(email, request).some((key) => {
    const state = getFreshState(key, now);
    if (state.lockUntil > now) {
      authAttemptState.set(key, state);
      return true;
    }
    return false;
  });
}

export function recordAuthFailure(email: string, request: Request | undefined) {
  const now = Date.now();

  for (const key of getAuthRateLimitKeys(email, request)) {
    const state = getFreshState(key, now);
    const failures = state.failures + 1;
    const nextState: AuthAttemptState = {
      failures,
      windowStartedAt: failures === 1 ? now : state.windowStartedAt,
      lockUntil: failures >= AUTH_MAX_FAILURES ? now + AUTH_LOCK_MS : 0,
    };
    authAttemptState.set(key, nextState);
  }
}

export function clearAuthFailures(email: string, request: Request | undefined) {
  for (const key of getAuthRateLimitKeys(email, request)) {
    authAttemptState.delete(key);
  }
}
