const INVALID_PERSON_TOKENS = new Set([
  "clinic",
  "clinics",
  "center",
  "centers",
  "hospital",
  "hospitals",
  "care",
  "health",
  "skin",
  "dental",
  "laser",
  "esthetic",
  "aesthetic",
  "cosmetic",
  "medspa",
  "spa",
  "group",
  "private",
  "limited",
  "pvt",
  "ltd",
  "llp",
  "llc",
  "brand",
  "owner",
  "hint",
  "iskin",
]);

function normalizePersonCandidate(value: string) {
  return value
    .replace(/\([^)]*\)/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function isPlausiblePersonName(value: string | null | undefined) {
  if (!value) {
    return false;
  }

  const cleaned = normalizePersonCandidate(String(value));
  if (!cleaned || cleaned.length < 4 || /\d/.test(cleaned)) {
    return false;
  }

  const tokens = cleaned
    .split(/\s+/)
    .map((token) => token.replace(/[.,]/g, "").trim())
    .filter(Boolean);

  if (tokens.length < 2) {
    return false;
  }

  const lowered = tokens.map((token) => token.toLowerCase());
  if (lowered.every((token) => INVALID_PERSON_TOKENS.has(token))) {
    return false;
  }

  if (lowered.some((token) => INVALID_PERSON_TOKENS.has(token))) {
    const nonGenericCount = lowered.filter(
      (token) => !INVALID_PERSON_TOKENS.has(token)
    ).length;
    if (nonGenericCount < 2) {
      return false;
    }
  }

  return tokens.every((token) => token.length >= 1);
}

export function sanitizeDecisionMakerName(value: string | null | undefined) {
  return isPlausiblePersonName(value) ? String(value).trim() : null;
}
