import type { AnalysisBundle, Lead, SignalFacts } from "@/lib/zrai/types";

export type PeopleIntelCandidate = NonNullable<SignalFacts["decision_maker_candidates"]>[number];
export type PeopleIntelDoctor = NonNullable<SignalFacts["doctor_profiles"]>[number];
export type PeopleIntelBranchContact = NonNullable<SignalFacts["branch_contacts"]>[number];

export type FounderIntelPayload = {
  doctor_names?: string[];
  doctor_profiles?: PeopleIntelDoctor[];
  branch_names?: string[];
  branch_contacts?: PeopleIntelBranchContact[];
  phone_numbers?: string[];
  emails?: string[];
  decision_maker_candidates?: PeopleIntelCandidate[];
  decision_maker_name?: string | null;
  decision_maker_role?: string | null;
  decision_maker_linkedin?: string | null;
  best_contact_phone?: string | null;
  best_contact_email?: string | null;
  best_contact_linkedin?: string | null;
  contact_evidence?: string[];
};

type ProcessedDetailsLike = {
  signal_facts?: SignalFacts | null;
  analysis_bundle?: AnalysisBundle | null;
};

type DecisionMakerStatus = NonNullable<SignalFacts["decision_maker_status"]>;

const GENERIC_EMAIL_DOMAINS = new Set([
  "gmail.com",
  "googlemail.com",
  "yahoo.com",
  "yahoo.co.in",
  "outlook.com",
  "hotmail.com",
  "live.com",
  "icloud.com",
  "proton.me",
  "protonmail.com",
  "rediffmail.com",
]);

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

function dedupeByName<T extends { name?: string | null }>(values: T[]) {
  const seen = new Set<string>();
  const deduped: T[] = [];

  for (const value of values) {
    const name = String(value?.name || "").trim();
    if (!name) {
      continue;
    }
    const key = name.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    deduped.push(value);
  }

  return deduped;
}

function normalizeContactKey(value: {
  name?: string | null;
  phone?: string | null;
  email?: string | null;
  linkedin?: string | null;
}) {
  const phone = String(value.phone || "").replace(/\D/g, "");
  if (phone.length >= 7) {
    return `phone:${phone}`;
  }
  const linkedin = String(value.linkedin || "").trim().toLowerCase();
  if (linkedin) {
    return `linkedin:${linkedin}`;
  }
  const email = String(value.email || "").trim().toLowerCase();
  if (email && !email.startsWith("frame-") && !email.endsWith("@example.com")) {
    return `email:${email}`;
  }
  const name = String(value.name || "").trim().toLowerCase();
  return name ? `name:${name}` : "";
}

function dedupeByIdentity<T extends { name?: string | null; phone?: string | null; email?: string | null; linkedin?: string | null }>(
  values: T[]
) {
  const seen = new Set<string>();
  const deduped: T[] = [];

  for (const value of values) {
    const key = normalizeContactKey(value);
    if (!key) {
      continue;
    }
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    deduped.push(value);
  }

  return deduped;
}

function normalizeEmail(value: string | null | undefined) {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized || !normalized.includes("@")) {
    return null;
  }
  if (normalized.startsWith("frame-")) {
    return null;
  }
  if (
    normalized.includes("@mht") ||
    normalized.includes("@mhtml") ||
    normalized.includes(".mht") ||
    normalized.includes(".mhtml") ||
    normalized.includes("cid:") ||
    normalized.includes("content-id")
  ) {
    return null;
  }
  if (normalized.endsWith("@example.com") || normalized.endsWith("@example.org")) {
    return null;
  }
  const localPart = normalized.split("@", 1)[0] || "";
  if (localPart.length > 48 && /\d/.test(localPart)) {
    return null;
  }
  return normalized;
}

function isGenericEmail(value: string | null | undefined) {
  const normalized = normalizeEmail(value);
  if (!normalized) {
    return false;
  }
  const domain = normalized.split("@", 1)[1] || "";
  return GENERIC_EMAIL_DOMAINS.has(domain);
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

function normalizeDecisionMakerStatus(value: unknown): SignalFacts["decision_maker_status"] {
  const normalized = String(value || "").trim().toLowerCase();

  switch (normalized) {
    case "verified":
    case "candidate":
    case "inferred":
    case "unknown":
      return normalized as DecisionMakerStatus;
    default:
      return null;
  }
}

function mergeSignalFacts(
  signalFacts: SignalFacts | null | undefined,
  founderIntel: FounderIntelPayload
): SignalFacts {
  const existing = (signalFacts || {}) as SignalFacts;
  const sanitizedFounderCandidates = (founderIntel.decision_maker_candidates || [])
    .map((candidate) => {
      const normalizedName = normalizePersonName(candidate?.name);
      const emails = (candidate?.emails || [])
        .map((email) => normalizeEmail(email))
        .filter(Boolean) as string[];
      return {
        ...candidate,
        name: normalizedName && isPlausiblePersonName(normalizedName) ? normalizedName : undefined,
        emails,
      };
    })
    .filter((candidate) => candidate.name || candidate.linkedin || candidate.phones?.length || candidate.emails?.length);
  const decisionMakerCandidates = dedupeByIdentity([
    ...sanitizedFounderCandidates,
    ...(existing.decision_maker_candidates || []),
  ]);
  const sanitizedFounderBranchContacts = (founderIntel.branch_contacts || []).filter(
    (contact) => Boolean(contact?.name || contact?.phone)
  );
  const branchContacts = dedupeByIdentity([
    ...sanitizedFounderBranchContacts,
    ...(existing.branch_contacts || []),
  ]);
  const doctorProfiles = dedupeByIdentity([...(existing.doctor_profiles || [])]);
  const doctorNames = dedupeStrings([
    ...(doctorProfiles.map((item) => item.name) || []),
    ...(existing.doctor_names || []),
  ]);
  const branchNames = dedupeStrings([
    ...(existing.branch_names || []),
  ]);
  const founderBestContactEmail = normalizeEmail(founderIntel.best_contact_email);
  const founderEmails = (founderIntel.emails || [])
    .map((email) => normalizeEmail(email))
    .filter(Boolean) as string[];
  const phoneNumbers = dedupeStrings([
    founderIntel.best_contact_phone || null,
    ...(branchContacts.map((item) => item.phone) || []),
    ...(existing.phone_numbers || []),
  ]);
  const emails = dedupeStrings([
    founderBestContactEmail,
    ...founderEmails,
    normalizeEmail(existing.best_contact_email),
  ]);
  const existingDecisionMakerStatus = normalizeDecisionMakerStatus(existing.decision_maker_status);
  const founderDecisionMakerName = normalizePersonName(founderIntel.decision_maker_name);
  const verifiedDecisionMakerName =
    existingDecisionMakerStatus === "verified" ? existing.decision_maker_name || null : null;
  const decisionMakerCandidateName =
    (founderDecisionMakerName && isPlausiblePersonName(founderDecisionMakerName)
      ? founderDecisionMakerName
      : null) ||
    decisionMakerCandidates[0]?.name ||
    existing.decision_maker_candidate_name ||
    (existingDecisionMakerStatus === "candidate" ? existing.decision_maker_name || null : null) ||
    null;
  const decisionMakerName = verifiedDecisionMakerName;
  const decisionMakerLinkedin =
    founderIntel.best_contact_linkedin ||
    founderIntel.decision_maker_linkedin ||
    decisionMakerCandidates[0]?.linkedin ||
    existing.best_contact_linkedin ||
    existing.decision_maker_linkedin ||
    null;
  const decisionMakerRole =
    founderIntel.decision_maker_role ||
    decisionMakerCandidates[0]?.role ||
    existing.decision_maker_role ||
    null;
  const bestContactPhone =
    founderIntel.best_contact_phone ||
    decisionMakerCandidates[0]?.phones?.[0] ||
    phoneNumbers[0] ||
    existing.best_contact_phone ||
    null;
  const bestContactEmail =
    founderBestContactEmail ||
    decisionMakerCandidates[0]?.emails?.[0] ||
    emails[0] ||
    existing.best_contact_email ||
    null;
  const contactEvidence = dedupeStrings([
    ...(founderIntel.contact_evidence || []),
    ...(existing.contact_evidence || []),
  ]);
  const decisionMakerStatus =
    existingDecisionMakerStatus === "verified"
      ? "verified"
      : decisionMakerCandidateName
        ? "candidate"
        : existingDecisionMakerStatus || null;

  return {
    ...existing,
    phone_numbers: phoneNumbers.length ? phoneNumbers : existing.phone_numbers,
    branch_names: branchNames.length ? branchNames : existing.branch_names,
    branch_count:
      existing.branch_count ??
      existing.branch_names?.length ??
      branchNames.length ??
      0,
    doctor_names: doctorNames.length ? doctorNames : existing.doctor_names,
    doctor_count:
      existing.doctor_count ??
      existing.doctor_names?.length ??
      doctorNames.length ??
      0,
    doctor_profiles: doctorProfiles.length ? doctorProfiles : existing.doctor_profiles,
    decision_maker_name: decisionMakerName,
    decision_maker_candidate_name: decisionMakerCandidateName,
    decision_maker_status: decisionMakerStatus,
    decision_maker_role: decisionMakerRole,
    decision_maker_linkedin: decisionMakerLinkedin,
    best_contact_phone: bestContactPhone,
    best_contact_email:
      !bestContactEmail || isGenericEmail(existing.best_contact_email) || !normalizeEmail(existing.best_contact_email)
        ? bestContactEmail
        : existing.best_contact_email,
    best_contact_linkedin: decisionMakerLinkedin,
    decision_maker_candidates: decisionMakerCandidates.length
      ? decisionMakerCandidates
      : existing.decision_maker_candidates,
    branch_contacts: branchContacts.length ? branchContacts : existing.branch_contacts,
    contact_evidence: contactEvidence.length ? contactEvidence : existing.contact_evidence,
  };
}

export function needsFounderIntelligence(
  lead: Lead | null | undefined,
  processedDetails: ProcessedDetailsLike | null | undefined
) {
  if (!lead?.domain && !(lead as any)?.website) {
    return false;
  }

  const signalFacts = processedDetails?.signal_facts || lead?.signal_facts || null;
  const decisionMakerCandidates = signalFacts?.decision_maker_candidates || [];
  const branchContacts = signalFacts?.branch_contacts || [];
  const hasDirectContactPath = Boolean(
    signalFacts?.best_contact_phone ||
      signalFacts?.best_contact_email ||
      signalFacts?.best_contact_linkedin
  );

  return Boolean(
    !signalFacts?.decision_maker_name ||
      (!hasDirectContactPath && !decisionMakerCandidates.length && !branchContacts.length)
  );
}

export async function fetchFounderIntelligence(lead: Lead) {
  const website = (lead as any).website || lead.domain || "";
  const response = await fetch("/api/zrai/founder-intel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      business_name: lead.company_name,
      website,
      location: lead.geo,
    }),
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  const payload = (await response.json()) as { success?: boolean; data?: FounderIntelPayload };
  return payload.data || {};
}

export function mergeFounderIntelligenceIntoProcessedDetails<T extends ProcessedDetailsLike | null | undefined>(
  processedDetails: T,
  founderIntel: FounderIntelPayload
) {
  const nextSignalFacts = mergeSignalFacts(processedDetails?.signal_facts, founderIntel);
  const nextAnalysisBundle = processedDetails?.analysis_bundle
    ? {
        ...processedDetails.analysis_bundle,
        facts: {
          ...(processedDetails.analysis_bundle.facts || {}),
          ...nextSignalFacts,
        },
        agent_context: {
          ...(processedDetails.analysis_bundle.agent_context || {}),
          decision_maker_name:
            nextSignalFacts.decision_maker_name ||
            processedDetails.analysis_bundle.agent_context?.decision_maker_name ||
            null,
          decision_maker_candidate_name:
            nextSignalFacts.decision_maker_candidate_name ||
            processedDetails.analysis_bundle.agent_context?.decision_maker_candidate_name ||
            null,
          decision_maker_status:
            nextSignalFacts.decision_maker_status ||
            processedDetails.analysis_bundle.agent_context?.decision_maker_status ||
            null,
          decision_maker_linkedin:
            founderIntel.best_contact_linkedin ||
            founderIntel.decision_maker_linkedin ||
            nextSignalFacts.best_contact_linkedin ||
            processedDetails.analysis_bundle.agent_context?.decision_maker_linkedin ||
            null,
          decision_maker_role:
            founderIntel.decision_maker_role ||
            nextSignalFacts.decision_maker_role ||
            processedDetails.analysis_bundle.agent_context?.decision_maker_role ||
            null,
          best_contact_phone:
            founderIntel.best_contact_phone ||
            nextSignalFacts.best_contact_phone ||
            processedDetails.analysis_bundle.agent_context?.best_contact_phone ||
            null,
          best_contact_email:
            founderIntel.best_contact_email ||
            nextSignalFacts.best_contact_email ||
            processedDetails.analysis_bundle.agent_context?.best_contact_email ||
            null,
          best_contact_linkedin:
            founderIntel.best_contact_linkedin ||
            nextSignalFacts.best_contact_linkedin ||
            processedDetails.analysis_bundle.agent_context?.best_contact_linkedin ||
            null,
          decision_maker_candidates:
            nextSignalFacts.decision_maker_candidates ||
            processedDetails.analysis_bundle.agent_context?.decision_maker_candidates,
          doctor_profiles:
            nextSignalFacts.doctor_profiles || processedDetails.analysis_bundle.agent_context?.doctor_profiles,
          branch_contacts:
            nextSignalFacts.branch_contacts || processedDetails.analysis_bundle.agent_context?.branch_contacts,
          contact_evidence:
            nextSignalFacts.contact_evidence || processedDetails.analysis_bundle.agent_context?.contact_evidence,
        },
      }
    : processedDetails?.analysis_bundle;

  return {
    ...(processedDetails || {}),
    signal_facts: nextSignalFacts,
    analysis_bundle: nextAnalysisBundle,
  } as T extends null | undefined ? ProcessedDetailsLike : T;
}
