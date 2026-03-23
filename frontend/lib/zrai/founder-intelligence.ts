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

function mergeSignalFacts(
  signalFacts: SignalFacts | null | undefined,
  founderIntel: FounderIntelPayload
): SignalFacts {
  const existing = (signalFacts || {}) as SignalFacts;
  const doctorProfiles = dedupeByName([
    ...(founderIntel.doctor_profiles || []),
    ...(existing.doctor_profiles || []),
  ]);
  const decisionMakerCandidates = dedupeByName([
    ...(founderIntel.decision_maker_candidates || []),
    ...(existing.decision_maker_candidates || []),
  ]);
  const branchContacts = dedupeByName([
    ...(founderIntel.branch_contacts || []),
    ...(existing.branch_contacts || []),
  ]);
  const doctorNames = dedupeStrings([
    ...(founderIntel.doctor_names || []),
    ...(doctorProfiles.map((item) => item.name) || []),
    ...(existing.doctor_names || []),
  ]);
  const branchNames = dedupeStrings([
    ...(founderIntel.branch_names || []),
    ...(branchContacts.map((item) => item.name) || []),
    ...(existing.branch_names || []),
  ]);
  const phoneNumbers = dedupeStrings([
    founderIntel.best_contact_phone || null,
    ...(founderIntel.phone_numbers || []),
    ...(branchContacts.map((item) => item.phone) || []),
    ...(existing.phone_numbers || []),
  ]);
  const emails = dedupeStrings([
    founderIntel.best_contact_email || null,
    ...(founderIntel.emails || []),
  ]);
  const decisionMakerName =
    founderIntel.decision_maker_name ||
    decisionMakerCandidates[0]?.name ||
    existing.decision_maker_name ||
    null;
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
    founderIntel.best_contact_email ||
    decisionMakerCandidates[0]?.emails?.[0] ||
    emails[0] ||
    existing.best_contact_email ||
    null;
  const contactEvidence = dedupeStrings([
    ...(founderIntel.contact_evidence || []),
    ...(existing.contact_evidence || []),
  ]);

  return {
    ...existing,
    phone_numbers: phoneNumbers.length ? phoneNumbers : existing.phone_numbers,
    branch_names: branchNames.length ? branchNames : existing.branch_names,
    branch_count:
      Math.max(existing.branch_count || 0, founderIntel.branch_names?.length || 0, branchContacts.length) || 0,
    doctor_names: doctorNames.length ? doctorNames : existing.doctor_names,
    doctor_count:
      Math.max(existing.doctor_count || 0, founderIntel.doctor_names?.length || 0, doctorProfiles.length) || 0,
    doctor_profiles: doctorProfiles.length ? doctorProfiles : existing.doctor_profiles,
    decision_maker_name: decisionMakerName,
    decision_maker_role: decisionMakerRole,
    decision_maker_linkedin: decisionMakerLinkedin,
    best_contact_phone: bestContactPhone,
    best_contact_email: bestContactEmail,
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

  return Boolean(
    !signalFacts?.decision_maker_name ||
      !decisionMakerCandidates.length ||
      !branchContacts.length ||
      !signalFacts?.doctor_count
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
            founderIntel.decision_maker_name ||
            nextSignalFacts.decision_maker_name ||
            processedDetails.analysis_bundle.agent_context?.decision_maker_name ||
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
