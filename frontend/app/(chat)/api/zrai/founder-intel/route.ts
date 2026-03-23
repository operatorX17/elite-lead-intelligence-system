import { auth } from "@/app/(auth)/auth";
import { authError, backendError, validationError } from "@/lib/zrai/errors";

const DISCOVERY_HTTP_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
  "Accept-Language": "en-US,en;q=0.9",
};

type Candidate = {
  name?: string;
  role?: string;
  source?: string;
  score?: number;
  linkedin?: string;
  emails?: string[];
  phones?: string[];
  clinic?: string;
};

function normalizeUrl(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  return trimmed.startsWith("http://") || trimmed.startsWith("https://")
    ? trimmed
    : `https://${trimmed.replace(/^\/+/, "")}`;
}

function normalizePhone(value: string | null | undefined) {
  if (!value) {
    return null;
  }

  const rawValue = String(value).trim();
  const digits = rawValue.replace(/\D/g, "");

  if (digits.length === 10) {
    if (/^[6-9]/.test(digits)) {
      return `+91${digits}`;
    }
    if (/[\s().-]/.test(rawValue) && /^[2-9]/.test(digits)) {
      return `+1${digits}`;
    }
    return null;
  }

  if (digits.length === 12 && digits.startsWith("91")) {
    return `+${digits}`;
  }

  if (digits.length === 11 && digits.startsWith("0") && /^[6-9]/.test(digits.slice(1))) {
    return `+91${digits.slice(1)}`;
  }

  if (digits.length === 11 && digits.startsWith("1")) {
    if (rawValue.startsWith("+1") || /[\s().-]/.test(rawValue)) {
      return `+${digits}`;
    }
    return null;
  }

  if (digits.length === 13 && digits.startsWith("091")) {
    return `+${digits.slice(1)}`;
  }

  if (digits.length > 10 && digits.length <= 13 && rawValue.startsWith("+")) {
    return `+${digits}`;
  }

  return null;
}

function dedupeStrings(values: Array<string | null | undefined>) {
  const seen = new Set<string>();
  const deduped: string[] = [];

  for (const value of values) {
    const normalized = String(value || "").trim();
    if (!normalized) {
      continue;
    }
    const key = normalized.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    deduped.push(normalized);
  }

  return deduped;
}

function dedupeByName<T extends { name?: string }>(items: T[]) {
  const seen = new Set<string>();
  const deduped: T[] = [];

  for (const item of items) {
    const name = String(item?.name || "").trim();
    if (!name) {
      continue;
    }
    const key = name.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    deduped.push(item);
  }

  return deduped;
}

function normalizePersonName(value: string | null | undefined) {
  if (!value) {
    return null;
  }

  const stripped = value
    .replace(/\bDr\.?\s*/gi, "")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^[^A-Za-z]+|[^A-Za-z.\s-]+$/g, "");

  if (!stripped) {
    return null;
  }

  const parts = stripped
    .split(" ")
    .map((part) => part.replace(/[^A-Za-z.-]/g, ""))
    .filter(Boolean)
    .map((part) => {
      if (part.length <= 2 && part === part.toUpperCase()) {
        return part;
      }
      return part.charAt(0).toUpperCase() + part.slice(1);
    });

  return parts.length >= 2 ? parts.join(" ") : null;
}

function looksLikeBusinessLabel(value: string) {
  const tokens = value
    .split(/\s+/)
    .map((token) => token.replace(/[.]/g, "").toLowerCase())
    .filter(Boolean);

  if (!tokens.length) {
    return true;
  }

  const blocked = new Set([
    "clinic",
    "skin",
    "hair",
    "laser",
    "care",
    "center",
    "centre",
    "hospital",
    "dermatology",
    "aesthetic",
    "aesthetics",
    "cosmetic",
    "cosmetology",
    "dental",
    "medspa",
    "med",
  ]);

  return tokens.some((token) => blocked.has(token));
}

function isPlausiblePersonName(value: string | null | undefined) {
  if (!value) {
    return false;
  }

  const tokens = value
    .split(/\s+/)
    .map((token) => token.replace(/\./g, "").trim())
    .filter(Boolean);
  const significantTokens = tokens.filter((token) => token.length > 1);

  if (significantTokens.length < 2 || looksLikeBusinessLabel(value)) {
    return false;
  }

  for (const token of tokens) {
    if (token.length <= 1 || token === token.toUpperCase()) {
      continue;
    }
    if (!/^[A-Z]/.test(token)) {
      return false;
    }
  }

  return true;
}

async function fetchText(url: string) {
  const response = await fetch(url, {
    headers: DISCOVERY_HTTP_HEADERS,
    next: { revalidate: 0 },
  });

  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }

  return response.text();
}

async function fetchWebsiteContent(website: string) {
  const normalized = normalizeUrl(website);
  if (!normalized) {
    return "";
  }

  let html = "";
  try {
    html = await fetchText(normalized);
  } catch {
    return "";
  }

  const parsed = new URL(normalized);
  const scriptMatches = Array.from(
    html.matchAll(/<script[^>]+src=["']([^"'#?]+(?:\.js|\.mjs)(?:\?[^"']*)?)["']/gi)
  )
    .map((match) => match[1])
    .filter(Boolean)
    .map((href) => new URL(href, normalized).toString())
    .filter((href) => new URL(href).host === parsed.host)
    .slice(0, 3);

  const assetTexts: string[] = [];
  for (const scriptUrl of scriptMatches) {
    try {
      const scriptText = await fetchText(scriptUrl);
      assetTexts.push(scriptText.slice(0, 750_000));
    } catch {
      // Ignore a single bundle failure.
    }
  }

  return [html, ...assetTexts].join("\n");
}

function buildDoctorProfile(name: string | null | undefined, specialty: string | null | undefined, experience: string | null | undefined, rawContext: string) {
  const normalizedName = normalizePersonName(name);
  if (!normalizedName || !isPlausiblePersonName(normalizedName)) {
    return null;
  }

  const lowerContext = String(rawContext || "").toLowerCase();
  const lowerSpecialty = String(specialty || "").toLowerCase();
  let role = "doctor";
  let score = 64;

  if (lowerSpecialty.includes("co-founder") || lowerSpecialty.includes("co founder")) {
    role = "co_founder";
    score = 95;
  } else if (lowerSpecialty.includes("founder") || lowerContext.includes("founder")) {
    role = "founder";
    score = 98;
  } else if (lowerSpecialty.includes("director") || lowerContext.includes("director")) {
    role = "director";
    score = 90;
  } else if (lowerSpecialty.includes("senior") || lowerContext.includes("senior dermatologist")) {
    role = "senior_doctor";
    score = 80;
  }

  const clinicMatch = rawContext.match(/iSkin\s+([A-Za-z]+)/i);
  const clinic = clinicMatch?.[1] || null;

  return {
    name: normalizedName,
    role,
    clinic,
    experience: experience || null,
    source: "website_asset",
    score,
    linkedin: null as string | null,
    phones: [] as string[],
    emails: [] as string[],
  };
}

function extractDoctorProfiles(rawContent: string) {
  const profiles: ReturnType<typeof buildDoctorProfile>[] = [];

  const objectPattern = /\{name:"(Dr\.[^"]+)"(?:,experience:"([^"]+)")?(?:,specialty:"([^"]+)")?/gi;
  const simplePattern = /\{name:"(Dr\.[^"]+)"(?:,[^{}]{0,180})?\}/gi;

  for (const match of rawContent.matchAll(objectPattern)) {
    const profile = buildDoctorProfile(match[1], match[3], match[2], match[0]);
    if (profile) {
      profiles.push(profile);
    }
  }

  for (const match of rawContent.matchAll(simplePattern)) {
    const profile = buildDoctorProfile(match[1], null, null, match[0]);
    if (profile) {
      profiles.push(profile);
    }
  }

  return dedupeByName(
    profiles.filter((item): item is NonNullable<typeof item> => Boolean(item)).sort((a, b) => (b.score || 0) - (a.score || 0))
  );
}

function extractBranchContacts(rawContent: string) {
  const contacts: Array<{ name: string; phone: string; source: string }> = [];
  const branchPattern = /\{name:"([A-Za-z][A-Za-z\s]+)",phone:"(\d{8,15})"\}/gi;

  for (const match of rawContent.matchAll(branchPattern)) {
    const name = String(match[1] || "").replace(/\s+/g, " ").trim();
    const phone = normalizePhone(match[2]);
    if (!name || !phone) {
      continue;
    }
    contacts.push({ name, phone, source: "website_asset" });
  }

  return dedupeByName(contacts);
}

async function searchLinkedin(name: string, businessName: string, location: string) {
  const query = encodeURIComponent(`"${name}" "${businessName}" linkedin ${location}`.trim());
  const url = `https://html.duckduckgo.com/html/?q=${query}`;

  try {
    const html = await fetchText(url);
    const linkedInMatch = html.match(/href="([^"]*linkedin\.com%2Fin%2F[^"]+|[^"]*linkedin\.com\/in\/[^"]+)"/i);
    if (!linkedInMatch?.[1]) {
      return null;
    }
    const rawHref = linkedInMatch[1]
      .replace(/&amp;/g, "&")
      .replace(/^\/l\/\?uddg=/, "");
    const decoded = decodeURIComponent(rawHref);
    if (decoded.includes("linkedin.com/in/")) {
      return decoded.split("&")[0];
    }
    return null;
  } catch {
    return null;
  }
}

async function buildFounderIntel(
  businessName: string,
  website: string,
  location: string
) {
  const rawContent = await fetchWebsiteContent(website);
  const doctorProfiles = extractDoctorProfiles(rawContent);
  const branchContacts = extractBranchContacts(rawContent);
  const doctorNames = dedupeStrings(doctorProfiles.map((profile) => profile?.name));
  const branchNames = dedupeStrings(branchContacts.map((contact) => contact.name));
  const phoneNumbers = dedupeStrings(branchContacts.map((contact) => contact.phone));

  for (const doctor of doctorProfiles.slice(0, 4)) {
    if (!doctor || doctor.linkedin) {
      continue;
    }
    const linkedin = await searchLinkedin(String(doctor.name || ""), businessName, location);
    if (linkedin) {
      doctor.linkedin = linkedin;
      doctor.score = Math.min((doctor.score || 0) + 4, 99);
    }
  }

  const decisionMakerCandidates: Candidate[] = dedupeByName(
    doctorProfiles
      .map((doctor) => ({
        name: doctor?.name,
        role: doctor?.role,
        source: doctor?.source,
        score: doctor?.score,
        linkedin: doctor?.linkedin || undefined,
        emails: doctor?.emails || [],
        phones: doctor?.phones || [],
        clinic: doctor?.clinic || undefined,
      }))
      .sort((a, b) => Number(b.score || 0) - Number(a.score || 0))
  );

  const bestCandidate = decisionMakerCandidates[0] || {};
  const bestContactPhone =
    normalizePhone(bestCandidate.phones?.[0]) || phoneNumbers[0] || null;
  const bestContactEmail = bestCandidate.emails?.[0] || null;
  const bestContactLinkedin = bestCandidate.linkedin || null;
  const contactEvidence = dedupeStrings([
    ...branchContacts.map((contact) => `${contact.name}: ${contact.phone}`),
    ...doctorProfiles
      .filter((doctor) => doctor?.name && doctor?.role)
      .map((doctor) => `${doctor.name} (${doctor.role})`),
  ]);

  return {
    doctor_names: doctorNames,
    doctor_profiles: doctorProfiles.slice(0, 8),
    branch_names: branchNames,
    branch_contacts: branchContacts.slice(0, 8),
    phone_numbers: phoneNumbers,
    emails: dedupeStrings([bestContactEmail]),
    decision_maker_candidates: decisionMakerCandidates.slice(0, 6),
    decision_maker_name: bestCandidate.name || null,
    decision_maker_role: bestCandidate.role || null,
    decision_maker_linkedin: bestContactLinkedin,
    best_contact_phone: bestContactPhone,
    best_contact_email: bestContactEmail,
    best_contact_linkedin: bestContactLinkedin,
    contact_evidence: contactEvidence.slice(0, 8),
  };
}

export async function POST(request: Request): Promise<Response> {
  try {
    const session = await auth();
    if (!session?.user) {
      return authError("leads").toResponse();
    }

    const body = (await request.json().catch(() => null)) as
      | { business_name?: string; website?: string; location?: string }
      | null;
    const businessName = String(body?.business_name || "").trim();
    const website = String(body?.website || "").trim();
    const location = String(body?.location || "").trim();

    if (!businessName || !website) {
      return validationError("leads", {
        message: "business_name and website are required",
      }).toResponse();
    }

    const data = await buildFounderIntel(businessName, website, location);
    return Response.json({ success: true, data });
  } catch (error) {
    console.error("[ZRAI:founder-intel] Error:", error);
    return backendError(
      "leads",
      error instanceof Error ? error.message : "Unknown error"
    ).toResponse();
  }
}
