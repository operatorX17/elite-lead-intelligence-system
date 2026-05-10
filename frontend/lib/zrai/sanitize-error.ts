/**
 * Operator-clean error sanitization for the inspector UI.
 *
 * Mirrors `_sanitize_operator_error` in src/api/server.py (and its railway
 * deploy mirror). Even though the backend now sanitizes before persistence,
 * historical rows and any future internal hiccup may still reach the UI -
 * we run a second-line scrubber here so operators NEVER see things like
 * "'ApifyClient' object has no attribute 'run_instagram_profile_scraper'"
 * or raw Python tracebacks.
 */
const PATTERNS: Array<[RegExp, string]> = [
  [/object has no attribute/i,
    "Live data temporarily unavailable. Re-analyze to refresh."],
  [/\bApifyClient\b|\bapify[_-]?client\b|apify\.com/i,
    "Live data source rate limited or quota exceeded. Retry shortly."],
  [/quota|insufficient.+credits|usage.+limit/i,
    "Live data quota exceeded. Maps/social refresh paused until quota resets."],
  [/timed?\s*out|timeout|ETIMEDOUT|read timed out/i,
    "Source took too long to respond. Try Re-analyze in a moment."],
  [/connection\s*(refused|reset|aborted)|EAI_AGAIN|getaddrinfo/i,
    "Network hiccup talking to a data source. Re-analyze to retry."],
  [/(?<![a-z])(json|parse|decode|unmarshal)(?![a-z])/i,
    "Source returned malformed data. Re-analyze to retry."],
  [/\b401\b|\b403\b|unauthor|forbidden|invalid.+key|api.?key/i,
    "A data source key needs attention. Operator action required."],
  [/\b5\d{2}\b|server error|bad gateway|service unavail/i,
    "Upstream source is temporarily unavailable. Retry shortly."],
];

export function sanitizeOperatorError(raw: unknown): string | null {
  if (raw === null || raw === undefined) return null;
  const text = String(raw).trim();
  if (!text) return null;
  if (["none", "null", "nan", "0", "undefined"].includes(text.toLowerCase())) return null;
  for (const [pattern, friendly] of PATTERNS) {
    if (pattern.test(text)) return friendly;
  }
  if (text.includes("Traceback") || (text.startsWith("<") && text.endsWith(">"))) {
    return "Last analysis hit an internal hiccup. Re-analyze to refresh.";
  }
  // Cap length so giant blobs never end up in the UI.
  if (text.length > 200) return text.slice(0, 197).trimEnd() + "...";
  return text;
}
