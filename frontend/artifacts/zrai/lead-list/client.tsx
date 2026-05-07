"use client";

/**
 * ZRAI Lead List Artifact - Client Component
 *
 * Displays a list of leads with filtering and sorting.
 */

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Artifact } from "@/components/create-artifact";
import { CopyIcon, RedoIcon, UndoIcon } from "@/components/icons";
import { useArtifact } from "@/hooks/use-artifact";
import {
  buildLeadScoreNarrative,
  buildRankedContactModel,
  formatLeadForClipboard,
  formatLeadListForClipboard,
} from "@/lib/zrai/clipboard";
import {
  fetchFounderIntelligence,
  mergeFounderIntelligenceIntoProcessedDetails,
  needsFounderIntelligence,
  type FounderIntelPayload,
} from "@/lib/zrai/founder-intelligence";
import { ensurePersistedLead, isUuidLeadId } from "@/lib/zrai/lead-resolution";
import type { AnalysisBundle, Lead, SignalFacts } from "@/lib/zrai/types";
import { getZRAILeadByIdEndpoint, ZRAI_ENDPOINTS } from "@/lib/zrai/constants";

type LeadListMetadata = {
  leads: Lead[];
  loading: boolean;
  sortBy: string;
  sortOrder: "asc" | "desc";
  filter: string;
  autoAnalyzeEnabled?: boolean;
  autoAnalyzeCompletedToken?: string | null;
  selectedLeadId?: string | null;
  processedDetails?: Record<string, ProcessedLeadDetails>;
  liveSelectedLead?: Lead | null;
  liveSelectedLeadDetails?: ProcessedLeadDetails | null;
};

type LeadListPayload = {
  autoAnalyzeEnabled?: boolean;
  autoAnalyzeCompletedToken?: string | null;
  filter?: string;
  leads?: Lead[];
  processedDetails?: Record<string, ProcessedLeadDetails>;
  processed_details?: Record<string, ProcessedLeadDetails>;
  selectedLeadId?: string | null;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
};

type ProcessedLeadDetails = {
  enrichment?: Record<string, unknown>;
  intent?: Record<string, unknown>;
  scoring?: Record<string, unknown>;
  error?: string;
  proof?: {
    hero_screenshot_url?: string;
    cta_screenshot_url?: string;
    audit_bullets?: Array<Record<string, string>>;
    extraction_data?: Record<string, unknown>;
  };
  outreach?: Array<{
    subject?: string;
    body?: string;
    channel?: string;
    status?: string;
  }>;
  signal_facts?: SignalFacts;
  analysis_bundle?: AnalysisBundle;
  analysis_state?: string;
  analysis_updated_at?: string;
  signals_version?: string;
};

type OutreachDraft = NonNullable<ProcessedLeadDetails["outreach"]>[number];

type ProcessedLeadResponseItem = {
  success: boolean;
  lead_id: string;
  error?: string;
  lead?: Lead;
  enrichment?: Record<string, unknown>;
  intent?: Record<string, unknown>;
  proof?: ProcessedLeadDetails["proof"];
  outreach?: ProcessedLeadDetails["outreach"];
  scoring?: ProcessedLeadDetails["scoring"];
  signal_facts?: SignalFacts;
  analysis_bundle?: AnalysisBundle;
  analysis_state?: string;
  analysis_updated_at?: string;
  signals_version?: string;
};

function getScoreResults(payload: any) {
  if (Array.isArray(payload?.results)) {
    return payload.results;
  }
  if (Array.isArray(payload?.data?.results)) {
    return payload.data.results;
  }
  return [];
}

function getPayloadData<T = any>(payload: any): T {
  return (payload?.data ?? payload) as T;
}

function getLeadSource(lead: Lead) {
  return (
    lead.source_label ||
    lead.intent_signals?.find((signal) => signal.signal_type === "discovery_source")
      ?.signal_value ||
    "Unknown"
  );
}

function getLeadFit(lead: Lead) {
  const rawFit = normalizeWhitespace(lead.verified_fit || lead.niche || "");
  if (!rawFit) {
    return "Candidate";
  }

  return rawFit
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\bwhatsapp\b/gi, "WhatsApp")
    .replace(/\bosint\b/gi, "OSINT")
    .replace(/\b([a-z])/g, (match: string) => match.toUpperCase());
}

function getLeadSummary(lead: Lead) {
  return (
    lead.preview_summary ||
    lead.intent_signals?.find((signal) => signal.signal_type === "summary")
      ?.signal_value ||
    ""
  );
}

function normalizeWhitespace(value: string | null | undefined) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

const LEAD_HOST_SUFFIX_TOKENS = [
  "clinics",
  "clinic",
  "premium",
  "aesthetics",
  "aesthetic",
  "dermatology",
  "cosmetics",
  "cosmetic",
  "vision",
  "laser",
  "medspa",
  "skin",
  "hair",
  "care",
  "center",
  "centre",
  "med",
  "spa",
];

function splitCompactLeadToken(token: string): string[] {
  const normalized = String(token || "").trim().toLowerCase();
  if (!normalized) {
    return [];
  }

  for (const suffix of LEAD_HOST_SUFFIX_TOKENS) {
    if (
      normalized.endsWith(suffix) &&
      normalized.length > suffix.length + 2
    ) {
      const prefix = normalized.slice(0, -suffix.length);
      return [...splitCompactLeadToken(prefix), suffix];
    }
  }

  return [normalized];
}

function stripLeadPhoneSuffix(value: string | null | undefined) {
  return normalizeWhitespace(value).replace(/\s*\+?\d[\d\s().-]{6,}$/g, "").trim();
}

function sanitizeLeadEmailValue(value: string | null | undefined) {
  const email = String(value || "").trim().toLowerCase();
  if (!email) {
    return "";
  }
  if (
    email.startsWith("frame-") ||
    email.includes("@mht") ||
    email.includes("@mhtml") ||
    email.endsWith("@example.com") ||
    email.endsWith("@example.org")
  ) {
    return "";
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return "";
  }
  return email;
}

function sanitizeLeadPhoneValue(value: string | null | undefined) {
  const phone = normalizeWhitespace(value);
  if (!phone) {
    return "";
  }
  const digits = phone.replace(/\D+/g, "");
  if (digits.length < 7) {
    return "";
  }
  return phone;
}

function dedupeStringValues(values: Array<string | null | undefined>) {
  return Array.from(
    new Set(values.map((value) => normalizeWhitespace(value)).filter(Boolean))
  );
}

function titleCaseLeadHostLabel(value: string) {
  return value
    .split(/[\s.-]+/)
    .filter(Boolean)
    .flatMap((part) => splitCompactLeadToken(part))
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatLeadHostLabel(host: string | null | undefined) {
  const normalizedHost = normalizeLeadDomainValue(host);
  if (!normalizedHost) {
    return "";
  }

  const label = normalizedHost.split(".")[0] || normalizedHost;
  return titleCaseLeadHostLabel(label);
}

function extractLeadBrandPrefix(value: string | null | undefined) {
  const raw = stripLeadPhoneSuffix(value);
  if (!raw) {
    return "";
  }

  const prefix = raw.split(/[:|\-]/)[0]?.trim() || "";
  return normalizeWhitespace(prefix);
}

function isLikelyGenericLeadName(value: string | null | undefined) {
  const raw = normalizeWhitespace(value);
  const normalized = normalizeLeadCompanyValue(stripLeadPhoneSuffix(value));
  if (!normalized) {
    return false;
  }

  if (stripLeadPhoneSuffix(raw) !== raw) {
    return true;
  }

  if (/(^|\s)(best|top|premium|leading|number 1|no 1|#1)(\s|$)/.test(normalized)) {
    return true;
  }

  if (/\b(in|near)\s+[a-z]+\b/.test(normalized) && /\b(clinic|specialist|dermatologist|aesthetic|skin|hair)\b/.test(normalized)) {
    return true;
  }

  if (/^#?\d+\s+hair and skin clinic$/.test(normalized)) {
    return true;
  }

  return false;
}

function pickCanonicalLeadName(lead: Lead | null | undefined) {
  if (!lead) {
    return "";
  }

  const businessName = stripLeadPhoneSuffix(lead.business_name);
  const companyName = stripLeadPhoneSuffix(lead.company_name);
  const businessPrefix = extractLeadBrandPrefix(businessName);
  const companyPrefix = extractLeadBrandPrefix(companyName);
  const hostLabel = formatLeadHostLabel(getLeadWebsiteHostValue(lead) || lead.domain);
  const directCandidates = [businessName, companyName];

  for (const candidate of directCandidates) {
    if (candidate && !isLikelyGenericLeadName(candidate)) {
      if (
        hostLabel &&
        normalizeLeadCompanyValue(candidate) === normalizeLeadCompanyValue(hostLabel) &&
        !candidate.includes(" ") &&
        hostLabel.includes(" ")
      ) {
        return hostLabel;
      }
      return candidate;
    }
  }

  for (const candidate of [businessPrefix, companyPrefix]) {
    if (candidate && !isLikelyGenericLeadName(candidate)) {
      return candidate;
    }
  }

  return hostLabel;
}

function sanitizeLeadContacts(contacts: Lead["contacts"] | null | undefined) {
  const contactByIdentity = new Map<string, NonNullable<Lead["contacts"]>[number]>();

  function scoreContactQuality(contact: {
    name?: string;
    title?: string;
    phone?: string;
    email?: string;
    linkedin_url?: string;
  }) {
    const normalizedName = normalizeWhitespace(contact.name);
    const normalizedTitle = normalizeWhitespace(contact.title);
    const normalizedEmail = sanitizeLeadEmailValue(contact.email);
    const normalizedPhone = sanitizeLeadPhoneValue(contact.phone);
    let score = 0;

    if (normalizedPhone) {
      score += 5;
    }
    if (normalizedEmail) {
      score += /\b(gmail|yahoo|hotmail|outlook)\./i.test(normalizedEmail) ? 2 : 4;
    }
    if (normalizeWhitespace(contact.linkedin_url)) {
      score += 3;
    }
    if (normalizedName && normalizedName !== "Contact" && !isLikelyGenericLeadName(normalizedName)) {
      score += 2;
    }
    if (normalizedTitle) {
      score += 1;
    }

    return score;
  }

  for (const contact of contacts || []) {
    const name = normalizeWhitespace(contact?.name) || "Contact";
    const title = normalizeWhitespace(contact?.title);
    const phone = sanitizeLeadPhoneValue(contact?.phone);
    const email = sanitizeLeadEmailValue(contact?.email);
    const linkedinUrl = normalizeWhitespace(contact?.linkedin_url);

    if (!phone && !email && !linkedinUrl) {
      continue;
    }

    const normalizedLinkedin = linkedinUrl.toLowerCase();
    const identity =
      (normalizedLinkedin && `linkedin:${normalizedLinkedin}`) ||
      (phone && `phone:${phone}`) ||
      (email && `email:${email.toLowerCase()}`) ||
      [name.toLowerCase(), title.toLowerCase(), phone, email, normalizedLinkedin].join("|");

    const nextContact = {
      ...contact,
      name,
      title: title || undefined,
      phone: phone || undefined,
      email: email || undefined,
      linkedin_url: linkedinUrl || undefined,
    };
    const existing = contactByIdentity.get(identity);

    if (!existing || scoreContactQuality(nextContact) > scoreContactQuality(existing)) {
      contactByIdentity.set(identity, nextContact);
    }
  }

  return Array.from(contactByIdentity.values());
}

function normalizeBranchDisplayName(value: string | null | undefined) {
  let text = normalizeWhitespace(value);
  if (!text) {
    return "";
  }

  text = text.split(",")[0]?.trim() || text;
  text = text.replace(/\b\d{5,6}\b/g, "").trim();

  if (/^\d/.test(text)) {
    return "";
  }

  if (/\bjp nagar\b/i.test(text)) {
    return "JP Nagar";
  }
  if (/\bkoramangala\b/i.test(text)) {
    return "Koramangala";
  }
  if (/\bjayanagar\b/i.test(text)) {
    return "Jayanagar";
  }
  if (/\bindiranagar\b/i.test(text)) {
    return "Indiranagar";
  }
  if (/\bhsr\b/i.test(text)) {
    return "HSR Layout";
  }

  const lowered = text.toLowerCase();
  if (["bangalore", "bengaluru", "karnataka", "india"].includes(lowered)) {
    return "";
  }

  return text;
}

function getDisplayBranchNames(signalFacts: SignalFacts | null | undefined) {
  return dedupeStringValues(
    (signalFacts?.branch_names || []).map((value) => normalizeBranchDisplayName(value))
  );
}

function normalizeDoctorDisplayName(value: string | null | undefined) {
  const text = normalizeWhitespace(value);
  if (!text) {
    return "";
  }

  const lowered = text.toLowerCase();
  if (
    lowered === "consultant dermatologist" ||
    lowered === "dermatologist" ||
    lowered === "doctor" ||
    lowered === "clinic branch"
  ) {
    return "";
  }

  return text;
}

function getDisplayDoctorNames(signalFacts: SignalFacts | null | undefined) {
  const names = [
    ...(signalFacts?.doctor_names || []),
    ...((signalFacts?.doctor_profiles || []).map((profile) => profile.name || "")),
  ];

  return dedupeStringValues(names.map((value) => normalizeDoctorDisplayName(value)));
}

function getSignalFactConfidence(signalFacts: SignalFacts | null | undefined, key: string) {
  const confidence = signalFacts?.confidence_by_signal?.[key];
  return typeof confidence === "number" ? confidence : 0;
}

function isSourceBackedSignal(signalFacts: SignalFacts | null | undefined, key: string) {
  const evidenceLevel = String(signalFacts?.evidence_levels?.[key] || "").toLowerCase();
  return (
    evidenceLevel === "verified" ||
    evidenceLevel === "confirmed" ||
    getSignalFactConfidence(signalFacts, key) >= 0.9
  );
}

function getFactSourceLabel(signalFacts: SignalFacts | null | undefined, key: string) {
  const source = String(signalFacts?.fact_sources?.[key] || "").toLowerCase();
  if (!source || source === "not_verified") {
    return "not verified";
  }
  if (source === "google_maps") {
    return "Google Maps";
  }
  if (source === "google_maps_cached") {
    return "Google Maps (cached)";
  }
  if (source === "website_contact_page") {
    return "website contact page";
  }
  if (source === "website_corroborated") {
    return "website corroborated";
  }
  if (source === "website_doctor_profile") {
    return "website doctor profile";
  }
  if (source === "website_text") {
    return "website text";
  }
  if (source === "website_or_maps") {
    return "website or Maps";
  }
  if (source === "website_instagram_link") {
    return "website Instagram link";
  }
  if (source === "apify_instagram_profile_scraper") {
    return "Instagram profile scrape";
  }
  if (source === "apify_instagram_bio_extractor") {
    return "Instagram bio scrape";
  }
  if (source === "website_youtube_link") {
    return "website YouTube link";
  }
  if (source === "apify_youtube_scraper") {
    return "YouTube scrape";
  }
  return source.replace(/_/g, " ");
}

function sanitizeSignalFactsForDisplay(signalFacts: SignalFacts | null | undefined) {
  if (!signalFacts) {
    return null;
  }

  const multiClinicSourceBacked = isSourceBackedSignal(signalFacts, "multi_clinic");
  const doctorsSourceBacked = isSourceBackedSignal(signalFacts, "doctors");
  const branchNames = multiClinicSourceBacked ? getDisplayBranchNames(signalFacts) : [];
  const doctorNames = doctorsSourceBacked ? getDisplayDoctorNames(signalFacts) : [];
  const rawBranchCount = Number(signalFacts.branch_count || 0);
  const rawDoctorCount = Number(signalFacts.doctor_count || 0);
  const branchCount =
    branchNames.length > 0
      ? branchNames.length
      : multiClinicSourceBacked
        ? rawBranchCount
        : 0;
  const doctorCount =
    doctorNames.length > 0
      ? doctorNames.length
      : doctorsSourceBacked
        ? rawDoctorCount
        : 0;

  return {
    ...signalFacts,
    branch_names: branchNames,
    branch_count: branchCount,
    multi_clinic: branchCount > 1,
    doctor_names: doctorNames,
    doctor_count: doctorCount,
  };
}

function sanitizeLeadRecord(lead: Lead): Lead {
  const canonicalName = pickCanonicalLeadName(lead);
  const businessNameMatchesCanonical =
    canonicalName &&
    normalizeLeadCompanyValue(lead.business_name) === normalizeLeadCompanyValue(canonicalName);
  const companyNameMatchesCanonical =
    canonicalName &&
    normalizeLeadCompanyValue(lead.company_name) === normalizeLeadCompanyValue(canonicalName);
  const cleanedBusinessName =
    !isLikelyGenericLeadName(lead.business_name) &&
    normalizeWhitespace(lead.business_name) &&
    !(businessNameMatchesCanonical && !normalizeWhitespace(lead.business_name).includes(" ") && canonicalName.includes(" "))
      ? normalizeWhitespace(lead.business_name)
      : canonicalName || normalizeWhitespace(lead.business_name);
  const cleanedCompanyName =
    !isLikelyGenericLeadName(lead.company_name) &&
    normalizeWhitespace(lead.company_name) &&
    !(companyNameMatchesCanonical && !normalizeWhitespace(lead.company_name).includes(" ") && canonicalName.includes(" "))
      ? normalizeWhitespace(lead.company_name)
      : canonicalName || normalizeWhitespace(lead.company_name);

  return {
    ...lead,
    business_name: cleanedBusinessName || undefined,
    company_name:
      cleanedCompanyName ||
      cleanedBusinessName ||
      formatLeadHostLabel(getLeadWebsiteHostValue(lead) || lead.domain) ||
      lead.company_name,
    contacts: sanitizeLeadContacts(lead.contacts),
    contact_paths: dedupeStringValues(lead.contact_paths || []),
    signal_facts: sanitizeSignalFactsForDisplay(lead.signal_facts) || undefined,
  };
}

function normalizeLeadUrlValue(value: string | null | undefined) {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) {
    return "";
  }

  const normalizedInput = /^[a-z]+:\/\//.test(raw) ? raw : `https://${raw}`;
  try {
    const parsed = new URL(normalizedInput);
    return parsed.hostname.replace(/^www\./, "").replace(/:\d+$/, "").trim();
  } catch {
    return normalizeLeadDomainValue(raw);
  }
}

function getLeadWebsiteHostValue(lead: Lead | null | undefined) {
  if (!lead) {
    return "";
  }

  return (
    normalizeLeadUrlValue(lead.website) ||
    normalizeLeadUrlValue(lead.landing_page_url) ||
    normalizeLeadUrlValue(lead.source_url) ||
    normalizeLeadUrlValue(lead.url)
  );
}

function getLeadDisplayName(lead: Lead | null | undefined) {
  if (!lead) {
    return "unknown lead";
  }

  const canonicalName = pickCanonicalLeadName(lead);
  if (canonicalName) {
    return canonicalName;
  }

  const websiteHost = getLeadWebsiteHostValue(lead);
  if (websiteHost) {
    return formatLeadHostLabel(websiteHost) || websiteHost;
  }

  const domain = normalizeLeadDomainValue(lead.domain);
  if (domain) {
    return formatLeadHostLabel(domain) || domain;
  }

  return lead.id || "unknown lead";
}

function hasLeadIdentity(lead: Lead | null | undefined) {
  if (!lead) {
    return false;
  }

  return Boolean(
    lead.id ||
      normalizeLeadDomainValue(lead.domain) ||
      getLeadWebsiteHostValue(lead) ||
      normalizeLeadCompanyValue(lead.business_name || lead.company_name)
  );
}

function getScoreLabel(lead: Lead) {
  if (lead.analysis_state === "analyzed" || lead.score_kind === "final_score") {
    return "Final";
  }
  return "Preview";
}

function getAnalysisLabel(lead: Lead) {
  if (lead.analysis_state === "failed") {
    return "Failed";
  }
  if (lead.analysis_state === "analyzing") {
    return "Analyzing";
  }
  return lead.analysis_state === "analyzed" || lead.score_kind === "final_score"
    ? "Analyzed"
    : "Preview";
}

function getResolvedAnalysisState(
  lead: Lead | null | undefined,
  processedDetails: ProcessedLeadDetails | null | undefined
) {
  if (
    processedDetails?.analysis_state === "failed" &&
    (lead?.analysis_state === "analyzed" || lead?.score_kind === "final_score")
  ) {
    return "analyzed";
  }
  return (
    processedDetails?.analysis_state ||
    lead?.analysis_state ||
    (lead?.score_kind === "final_score" ? "analyzed" : null)
  );
}

function isTerminalAnalysisState(
  lead: Lead | null | undefined,
  processedDetails: ProcessedLeadDetails | null | undefined
) {
  const state = getResolvedAnalysisState(lead, processedDetails);
  return state === "analyzed" || state === "failed";
}

function getStatusHelp(status: Lead["status"]) {
  switch (status) {
    case "qualified_preview":
      return "Discovery found a likely good lead, but the full chain has not been run yet.";
    case "candidate_preview":
      return "Discovery found a possible lead, but confidence is still weaker and needs validation.";
    case "enriched":
      return "The lead was enriched and contact data was pulled, but outreach is not drafted yet.";
    case "outreach_pending":
      return "The full chain ran and draft outreach is ready for review.";
    case "qualified":
      return "The lead is treated as high quality and ready for operator action.";
    default:
      return "Current pipeline stage for this lead.";
  }
}

function formatContactPath(path: string | undefined) {
  if (!path) {
    return "unknown";
  }

  return String(path)
    .replace(/_/g, " ")
    .replace(/\bcta\b/i, "CTA")
    .replace(/\bwhatsapp\b/i, "WhatsApp")
    .replace(/\bbooking\b/i, "booking link");
}

function formatLeadStatus(status: Lead["status"] | string | undefined) {
  if (!status) {
    return "unknown";
  }

  return String(status).replace(/_/g, " ");
}

function formatBooleanFact(value: unknown, truthyLabel: string, falsyLabel: string) {
  return value ? truthyLabel : falsyLabel;
}

function getWhatsAppFact(extractionData: Record<string, unknown> | undefined) {
  const target = extractionData?.whatsapp_target ? String(extractionData.whatsapp_target) : "";
  const widgetDetected = String(extractionData?.chat_widget || "").toLowerCase() === "whatsapp";
  return {
    hasWhatsApp: Boolean(target),
    widgetDetected,
    target: target || "not extracted",
  };
}

function getSignalFacts(
  lead: Lead | null | undefined,
  processedDetails: ProcessedLeadDetails | undefined
): SignalFacts | null {
  return sanitizeSignalFactsForDisplay(
    processedDetails?.signal_facts ||
    lead?.signal_facts ||
    null
  );
}

function getCanonicalProofFacts(
  signalFacts: SignalFacts | null,
  extractionData: Record<string, unknown> | undefined
) {
  const extractedPhoneNumbers = Array.isArray(extractionData?.phone_numbers)
    ? extractionData.phone_numbers.map((value) => String(value))
    : [];
  const phoneNumbers = signalFacts?.phone_numbers?.length
    ? signalFacts.phone_numbers
    : extractedPhoneNumbers;

  return {
    phoneVisible:
      signalFacts?.phone_visible ??
      (["hero", "visible", "above_fold", "below_fold"].includes(
        String(extractionData?.phone_visibility || "")
      ) || phoneNumbers.length > 0),
    phoneNumbers,
    bookingDetected: signalFacts?.booking_detected ?? Boolean(extractionData?.booking_link),
    bookingTarget:
      signalFacts?.booking_target ||
      (extractionData?.booking_link ? String(extractionData.booking_link) : null),
    whatsappDetected:
      signalFacts?.whatsapp_detected ??
      Boolean(extractionData?.whatsapp_target),
    whatsappWidgetDetected:
      signalFacts?.whatsapp_widget_detected ??
      String(extractionData?.chat_widget || "").toLowerCase() === "whatsapp",
    whatsappTarget:
      signalFacts?.whatsapp_target ||
      (extractionData?.whatsapp_target ? String(extractionData.whatsapp_target) : null),
    chatWidgetType:
      signalFacts?.chat_widget_type ||
      (extractionData?.chat_widget ? String(extractionData.chat_widget) : null),
    bookingFlowQuality:
      signalFacts?.booking_flow_quality ||
      ((signalFacts?.booking_detected ?? Boolean(extractionData?.booking_link)) ? "basic" : "none"),
  };
}

function getCanonicalProofInsights(
  signalFacts: SignalFacts | null,
  extractionData: Record<string, unknown> | undefined,
  fallbackBullets: Array<Record<string, string>> | undefined
) {
  if (!signalFacts) {
    return (fallbackBullets || [])
      .map((bullet) => bullet.evidence || bullet.specific || bullet.estimate || "")
      .filter(Boolean);
  }

  const facts = getCanonicalProofFacts(signalFacts, extractionData);
  const insights: string[] = [];

  insights.push(
    facts.phoneVisible
      ? "Phone contact is available on-site."
      : "Phone is not visibly promoted on the landing page."
  );

  if (!facts.whatsappDetected) {
    if (facts.whatsappWidgetDetected) {
      insights.push("WhatsApp widget is present, but the exact target was not cleanly extracted.");
    } else {
      insights.push("WhatsApp capture path is missing.");
    }
  } else if (!facts.whatsappTarget) {
    insights.push("WhatsApp is present, but the exact target was not cleanly extracted.");
  } else {
    insights.push(`WhatsApp path detected: ${facts.whatsappTarget}`);
  }

  if (!facts.bookingDetected) {
    insights.push("Booking path was not detected.");
  } else if (facts.bookingFlowQuality === "weak") {
    insights.push("Booking exists, but the flow quality still looks weak.");
  } else {
    insights.push("Booking path detected.");
  }

  if (signalFacts.next_best_action) {
    insights.push(signalFacts.next_best_action);
  }

  return insights.slice(0, 4);
}

function formatLocationFact(signalFacts: SignalFacts) {
  const cleanedBranchNames = getDisplayBranchNames(signalFacts);
  const branchCount = cleanedBranchNames.length || signalFacts.branch_count || 0;
  if (branchCount > 1) {
    return String(branchCount);
  }
  if (branchCount === 1) {
    return "1";
  }
  return "-";
}

function formatAdsFact(signalFacts: SignalFacts) {
  if (signalFacts.ads_status === "yes") {
    return signalFacts.ads_active_count ? `${signalFacts.ads_active_count} live` : "Active";
  }
  if (signalFacts.ads_status === "no") {
    return "No";
  }
  return "Not checked";
}

function formatSocialCount(value: number | null | undefined, noun: string) {
  if (value == null) {
    return "-";
  }
  return `${new Intl.NumberFormat("en-US", { notation: value >= 1000 ? "compact" : "standard" }).format(value)} ${noun}`;
}

function formatSocialMetric(value: number | null | undefined) {
  if (value == null) {
    return "-";
  }
  return new Intl.NumberFormat("en-US", { notation: value >= 1000 ? "compact" : "standard" }).format(value);
}

function formatSocialDate(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString("en-IN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function buildInstagramBehaviorSummary(signalFacts: SignalFacts) {
  const profile = signalFacts.instagram_profile;
  if (!profile) {
    return signalFacts.instagram_present ? "Instagram profile detected" : "No Instagram profile";
  }
  const notes = [
    profile.verified ? "verified profile" : null,
    profile.is_business_account ? "business account" : null,
    profile.business_category ? profile.business_category : null,
    profile.latest_post_count != null && profile.latest_post_count > 0
      ? `${profile.latest_post_count} recent posts captured`
      : null,
    profile.posts_count != null && profile.posts_count >= 150
      ? "large content archive"
      : profile.posts_count != null && profile.posts_count >= 40
        ? "steady publishing history"
        : profile.posts_count != null && profile.posts_count > 0
          ? "light content history"
          : null,
  ].filter(Boolean);
  return notes.length ? notes.join(" | ") : "Instagram profile linked";
}

function buildYouTubeBehaviorSummary(signalFacts: SignalFacts) {
  const channel = signalFacts.youtube_channel;
  if (!channel) {
    return signalFacts.youtube_present ? "YouTube channel detected" : "No YouTube channel";
  }
  const notes = [
    channel.recent_video_count != null && channel.recent_video_count > 0
      ? `${channel.recent_video_count} recent videos scraped`
      : null,
    channel.avg_recent_views != null && channel.avg_recent_views > 0
      ? `${formatSocialMetric(channel.avg_recent_views)} avg recent views`
      : null,
    channel.total_videos != null && channel.total_videos >= 100
      ? "large video library"
      : channel.total_videos != null && channel.total_videos >= 20
        ? "consistent publishing history"
        : channel.total_videos != null && channel.total_videos > 0
          ? "small video library"
          : null,
    channel.latest_video_date ? `latest upload ${formatSocialDate(channel.latest_video_date)}` : null,
  ].filter(Boolean);
  return notes.length ? notes.join(" | ") : "YouTube channel linked";
}

function buildSocialResearchSummary(signalFacts: SignalFacts) {
  const lines = [
    signalFacts.ads_status === "yes"
      ? signalFacts.ads_active_count
        ? `Meta ads active: ${signalFacts.ads_active_count}`
        : "Meta ads active"
      : null,
    signalFacts.instagram_profile?.followers_count
      ? `Instagram: ${signalFacts.instagram_profile.followers_count} followers`
      : signalFacts.instagram_present
        ? "Instagram profile detected"
        : null,
    signalFacts.youtube_channel?.subscriber_count
      ? `YouTube: ${signalFacts.youtube_channel.subscriber_count} subscribers`
      : signalFacts.youtube_present
        ? "YouTube channel detected"
        : null,
  ].filter(Boolean);

  return lines.length ? lines.join(" | ") : null;
}

function formatAdsStatus(adsStatus: SignalFacts["ads_status"] | undefined) {
  if (adsStatus === "yes") {
    return "Yes";
  }
  if (adsStatus === "no") {
    return "No";
  }
  return "Not checked";
}

function getTopIssue(signalFacts: SignalFacts | null) {
  if (!signalFacts) {
    return "No analyzed truth yet";
  }
  if (signalFacts.top_issue) {
    return signalFacts.top_issue;
  }
  if (!signalFacts.phone_visible) {
    return "Phone is not prominent";
  }
  if (!signalFacts.whatsapp_detected) {
    return signalFacts.whatsapp_widget_detected
      ? "WhatsApp widget is present, but the exact target was not cleanly extracted"
      : "WhatsApp capture is missing";
  }
  if (!signalFacts.booking_detected || signalFacts.booking_flow_quality === "weak") {
    return "Booking flow is weak";
  }
  if (!signalFacts.after_hours_capture) {
    return "No after-hours capture";
  }
  return "Conversion optimization opportunity";
}

function getNextBestAction(signalFacts: SignalFacts | null) {
  if (!signalFacts) {
    return "Analyze this lead";
  }
  if (signalFacts.next_best_action) {
    return signalFacts.next_best_action;
  }
  if (!signalFacts.phone_visible) {
    return "Make phone visible in header and hero";
  }
  if (!signalFacts.whatsapp_detected) {
    return signalFacts.whatsapp_widget_detected
      ? "Confirm the WhatsApp entry path and autoresponse"
      : "Add WhatsApp entry path and autoresponse";
  }
  if (!signalFacts.booking_detected || signalFacts.booking_flow_quality === "weak") {
    return "Fix booking flow and confirmation path";
  }
  if (!signalFacts.instant_response_path) {
    return "Add instant response automation";
  }
  return "Pitch AI conversion plumbing upgrade";
}

function getVisibleOutreachDrafts(outreach: ProcessedLeadDetails["outreach"] | undefined) {
  if (!outreach?.length) {
    return { drafts: [] as OutreachDraft[], hiddenCount: 0 };
  }

  const seen = new Set<string>();
  const uniqueDrafts: OutreachDraft[] = [];

  for (const draft of [...outreach].reverse()) {
    const signature = JSON.stringify({
      channel: draft.channel || "",
      subject: (draft.subject || "").trim(),
      body: (draft.body || "").replace(/\s+/g, " ").trim(),
    });

    if (seen.has(signature)) {
      continue;
    }

    seen.add(signature);
    uniqueDrafts.push(draft);
  }

  return {
    drafts: uniqueDrafts.slice(0, 2),
    hiddenCount: Math.max(uniqueDrafts.length - 2, 0),
  };
}

function getAnalysisBundle(
  lead: Lead | null | undefined,
  processedDetails: ProcessedLeadDetails | undefined
) {
  return processedDetails?.analysis_bundle || lead?.analysis_bundle || null;
}

function hydrateLeadFromStoredAnalysis(
  lead: Lead | null | undefined,
  processedDetails: ProcessedLeadDetails | null | undefined
) {
  if (!lead) {
    return null;
  }

  if (!processedDetails?.analysis_state) {
    return lead;
  }

  if (processedDetails.analysis_state !== "analyzed") {
    if (lead.analysis_state === "analyzed" || lead.score_kind === "final_score") {
      return sanitizeLeadRecord(lead) as Lead;
    }
    return sanitizeLeadRecord({
      ...lead,
      analysis_state: processedDetails.analysis_state as Lead["analysis_state"],
      analysis_updated_at: processedDetails.analysis_updated_at || lead.analysis_updated_at,
    }) as Lead;
  }

  const analysisBundle = getAnalysisBundle(lead, processedDetails || undefined);
  const scoring = (processedDetails?.scoring || {}) as Record<string, unknown>;
  const scores = analysisBundle?.scores || {};
  const scoreBreakdown = (scoring.score_breakdown || scoring.breakdown || {}) as Record<string, unknown>;
  const storedFinalScore =
    (scores.final_score as number | undefined) ??
    (scores.total_score as number | undefined) ??
    (scoreBreakdown.total_score as number | undefined) ??
    null;
  const finalScore =
    storedFinalScore ??
    lead.final_score ??
    lead.score ??
    null;

  return sanitizeLeadRecord({
    ...lead,
    score: finalScore ?? lead.score,
    final_score: finalScore ?? lead.final_score,
    score_kind: "final_score" as const,
    analysis_state: "analyzed" as const,
    analysis_updated_at: processedDetails.analysis_updated_at || lead.analysis_updated_at,
    signals_version: processedDetails.signals_version || lead.signals_version,
    signal_facts: processedDetails.signal_facts || lead.signal_facts,
  }) as Lead;
}

function getScoreSnapshot(
  lead: Lead | null | undefined,
  processedDetails: ProcessedLeadDetails | undefined
) {
  const analysisBundle = getAnalysisBundle(lead, processedDetails);
  const scoring = (processedDetails?.scoring || {}) as Record<string, unknown>;
  const scoreBreakdown = (scoring.score_breakdown || scoring.breakdown || {}) as Record<string, unknown>;
  const scores = analysisBundle?.scores || {};
  const storedFinalScore =
    (scores.final_score as number | undefined) ??
    (scores.total_score as number | undefined) ??
    (scoreBreakdown.total_score as number | undefined) ??
    null;
  const finalScore =
    storedFinalScore ??
    lead?.final_score ??
    lead?.score ??
    null;

  return {
    finalScore,
    demand: (scores.demand_score as number | undefined) ?? (scoreBreakdown.demand_score as number | undefined) ?? null,
    trust: (scores.trust_score as number | undefined) ?? (scoreBreakdown.trust_score as number | undefined) ?? null,
    leak: (scores.leak_score as number | undefined) ?? (scoreBreakdown.leak_score as number | undefined) ?? null,
    serviceability:
      (scores.serviceability_score as number | undefined) ??
      (scoreBreakdown.serviceability_score as number | undefined) ??
      null,
    offerFit:
      (scores.offer_fit_score as number | undefined) ??
      (scoreBreakdown.offer_fit_score as number | undefined) ??
      null,
  };
}

function formatBestContactChannel(value: string | null | undefined) {
  if (!value) {
    return "-";
  }

  return String(value)
    .replace(/_/g, " ")
    .replace(/\bwhatsapp\b/i, "WhatsApp")
    .replace(/\blinkedin\b/i, "LinkedIn");
}

function getContactIntelligence(
  lead: Lead | null,
  processedDetails: ProcessedLeadDetails | null | undefined,
  signalFacts: SignalFacts | null,
  analysisBundle: AnalysisBundle | null
) {
  const rankedContacts = buildRankedContactModel(lead, processedDetails || null);
  const scoreNarrative = buildLeadScoreNarrative(lead, processedDetails || null);
  const topContact = rankedContacts.topContact;
  const doctorNames = getDisplayDoctorNames(signalFacts);
  const decisionMakerCandidates =
    (signalFacts?.decision_maker_candidates || analysisBundle?.agent_context?.decision_maker_candidates || []).map((candidate) => ({
      ...candidate,
      phones: dedupeStringValues((candidate.phones || []).map((value) => sanitizeLeadPhoneValue(value))),
      emails: dedupeStringValues((candidate.emails || []).map((value) => sanitizeLeadEmailValue(value))),
      email: sanitizeLeadEmailValue((candidate as { email?: string | null }).email),
      phone: sanitizeLeadPhoneValue((candidate as { phone?: string | null }).phone),
    })).filter((candidate) => Boolean(
      normalizeDoctorDisplayName(String(candidate.name || "")) ||
      candidate.phones?.length ||
      candidate.emails?.length ||
      candidate.phone ||
      candidate.email
    ));
  const branchContacts = (signalFacts?.branch_contacts || analysisBundle?.agent_context?.branch_contacts || [])
    .map((contact) => ({
      ...contact,
      name: normalizeBranchDisplayName(contact.name || "Clinic branch") || "Clinic branch",
      phone: sanitizeLeadPhoneValue(contact.phone),
    }))
    .filter((contact) => Boolean(contact.phone));

  return {
    ...rankedContacts,
    scoreNarrative,
    decisionMakerName: rankedContacts.decisionMakerName,
    decisionMakerLinkedin:
      rankedContacts.decisionMakerLinkedin || topContact?.linkedin || null,
    decisionMakerRole:
      rankedContacts.decisionMakerRole || topContact?.role || null,
    decisionMakerSource:
      rankedContacts.decisionMakerSource || topContact?.source || null,
    decisionMakerConfidence:
      rankedContacts.decisionMakerConfidence ?? topContact?.score ?? null,
    bestContactPhone:
      rankedContacts.bestContactPhone || topContact?.phone || null,
    bestContactEmail:
      rankedContacts.bestContactEmail || topContact?.email || null,
    bestContactChannel:
      rankedContacts.bestContactChannel || topContact?.channel || null,
    bestContactReason:
      rankedContacts.bestContactReason || topContact?.reason || null,
    recommendedOffer: rankedContacts.recommendedOffer,
    doctorNames,
    decisionMakerCandidates,
    branchContacts,
    hasAny: Boolean(
      rankedContacts.topContact ||
        rankedContacts.alternateContacts.length ||
        rankedContacts.contactEvidence.length ||
        rankedContacts.bestContactReason ||
        scoreNarrative.whyThisLead ||
        scoreNarrative.trustSummary ||
        scoreNarrative.leakSummary ||
        scoreNarrative.offerFitSummary ||
        doctorNames.length
    ),
  };
}

function getDecisionLabel(finalScore: number | null | undefined) {
  if (finalScore == null) {
    return "Needs analysis";
  }
  if (finalScore >= 75) {
    return "High-priority";
  }
  if (finalScore >= 60) {
    return "Worth pursuing";
  }
  if (finalScore >= 45) {
    return "Conditional";
  }
  return "Low priority";
}

function getLeadRowPriority(lead: Lead) {
  let score = 0;
  if (lead.score_kind === "final_score") {
    score += 10;
  }
  if (lead.analysis_state === "analyzed") {
    score += 8;
  } else if (lead.analysis_state === "analyzing") {
    score += 2;
  }
  if ((lead.contacts?.length || 0) > 0) {
    score += 3;
  }
  if (lead.source && lead.source !== "Unknown") {
    score += 1;
  }
  if (lead.score != null) {
    score += 1;
  }
  return score;
}

function mergeLeadRecord(existing: Lead | null | undefined, incoming: Lead) {
  if (!existing) {
    return sanitizeLeadRecord(incoming);
  }

  const cleanedExisting = sanitizeLeadRecord(existing);
  const cleanedIncoming = sanitizeLeadRecord(incoming);
  const existingWins = getLeadRowPriority(cleanedExisting) > getLeadRowPriority(cleanedIncoming);
  const primary = existingWins ? cleanedExisting : cleanedIncoming;
  const secondary = existingWins ? cleanedIncoming : cleanedExisting;

  return sanitizeLeadRecord({
    ...secondary,
    ...primary,
    business_name: pickCanonicalLeadName(primary) || pickCanonicalLeadName(secondary) || primary.business_name || secondary.business_name,
    company_name: pickCanonicalLeadName(primary) || pickCanonicalLeadName(secondary) || primary.company_name || secondary.company_name,
    contacts:
      sanitizeLeadContacts(primary.contacts).length > 0
        ? sanitizeLeadContacts(primary.contacts)
        : sanitizeLeadContacts(secondary.contacts),
    contact_paths: dedupeStringValues([...(secondary.contact_paths || []), ...(primary.contact_paths || [])]),
    signal_facts: sanitizeSignalFactsForDisplay(primary.signal_facts) || sanitizeSignalFactsForDisplay(secondary.signal_facts) || undefined,
    analysis_bundle: primary.analysis_bundle ?? secondary.analysis_bundle,
  });
}

function isSameLeadEntity(a: Lead | null | undefined, b: Lead | null | undefined) {
  if (!a || !b) {
    return false;
  }

  if (a.id && b.id && a.id === b.id) {
    return true;
  }

  const aIdentity = getNormalizedLeadIdentity(a);
  const bIdentity = getNormalizedLeadIdentity(b);

  if (aIdentity.domain && bIdentity.domain && aIdentity.domain === bIdentity.domain) {
    return true;
  }

  if (aIdentity.website && bIdentity.website && aIdentity.website === bIdentity.website) {
    return true;
  }

  if (aIdentity.domain && bIdentity.website && aIdentity.domain === bIdentity.website) {
    return true;
  }

  if (aIdentity.website && bIdentity.domain && aIdentity.website === bIdentity.domain) {
    return true;
  }

  const companyMatches =
    aIdentity.company &&
    bIdentity.company &&
    aIdentity.company === bIdentity.company;
  const domainConflicts =
    Boolean(aIdentity.domain && bIdentity.domain && aIdentity.domain !== bIdentity.domain);
  const websiteConflicts =
    Boolean(aIdentity.website && bIdentity.website && aIdentity.website !== bIdentity.website);

  if (companyMatches && !domainConflicts && !websiteConflicts) {
    return true;
  }

  return false;
}

function getCanonicalLeadEntityKey(lead: Lead | null | undefined) {
  if (!lead) {
    return "";
  }

  const identity = getNormalizedLeadIdentity(lead);
  const siteKey = identity.domain || identity.website;
  if (siteKey) {
    return `site:${siteKey}`;
  }
  if (identity.company) {
    return `company:${identity.company}`;
  }
  return `id:${lead.id || "lead"}`;
}

function findMergedLeadEntryByEntity(
  mergedRows: Map<string, Lead>,
  target: Lead
) {
  for (const [entityKey, lead] of mergedRows.entries()) {
    if (isSameLeadEntity(lead, target)) {
      return [entityKey, lead] as const;
    }
  }
  return null;
}

function mergeLeadRows(existing: Lead[], incoming: Lead[]) {
  const mergedRows = new Map<string, Lead>();

  const upsert = (lead: Lead) => {
    if (!lead?.id && !hasLeadIdentity(lead)) {
      return;
    }

    const entityKey = getCanonicalLeadEntityKey(lead);
    if (!entityKey) {
      return;
    }

    const matchingEntry = findMergedLeadEntryByEntity(mergedRows, lead);
    if (matchingEntry) {
      const [matchingKey, existingLead] = matchingEntry;
      mergedRows.set(matchingKey, mergeLeadRecord(existingLead, lead));
      return;
    }

    const existingLead = mergedRows.get(entityKey);
    if (existingLead) {
      mergedRows.set(entityKey, mergeLeadRecord(existingLead, lead));
      return;
    }

    mergedRows.set(entityKey, lead);
  };

  for (const lead of existing) {
    upsert(lead);
  }

  for (const lead of incoming) {
    upsert(lead);
  }

  return sanitizeLeadRows(Array.from(mergedRows.values()));
}

function dedupeLeadRows(leads: Lead[]) {
  return mergeLeadRows([], leads);
}

function sanitizeLeadRows(leads: Lead[]) {
  return leads
    .map((lead) => sanitizeLeadRecord(lead))
    .filter((lead) => Boolean(lead.id || hasLeadIdentity(lead)));
}

function normalizeLeadDomainValue(value: string | null | undefined) {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) {
    return "";
  }

  const withoutProtocol = raw.replace(/^[a-z]+:\/\//, "");
  const withoutWww = withoutProtocol.replace(/^www\./, "");
  const hostname = withoutWww.split(/[/?#]/)[0] || withoutWww;
  return hostname.replace(/:\d+$/, "").trim();
}

function normalizeLeadCompanyValue(value: string | null | undefined) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFKC")
    .replace(/[\u200B-\u200D\uFEFF]/g, "")
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function getNormalizedLeadIdentity(lead: Lead | null | undefined) {
  if (!lead) {
    return {
      domain: "",
      website: "",
      company: "",
    };
  }

  return {
    domain: normalizeLeadDomainValue(lead.domain),
    website: getLeadWebsiteHostValue(lead),
    company: normalizeLeadCompanyValue(lead.business_name || lead.company_name),
  };
}

function resolveSelectedLeadId(
  selectedLeadId: string | null | undefined,
  mergedLeads: Lead[],
  candidateLeads: Lead[]
) {
  if (!selectedLeadId) {
    return null;
  }

  if (mergedLeads.some((lead) => lead.id === selectedLeadId)) {
    return selectedLeadId;
  }

  const sourceLead = candidateLeads.find((lead) => lead.id === selectedLeadId);
  if (!sourceLead) {
    return null;
  }

  const remappedLead = findBestLeadByEntity(mergedLeads, sourceLead);

  return remappedLead?.id || null;
}

function findBestLeadByEntity(leads: Lead[], target: Lead | null | undefined) {
  if (!target) {
    return null;
  }

  const matches = leads.filter((lead) => isSameLeadEntity(lead, target));
  if (!matches.length) {
    return null;
  }

  return (
    matches.sort((a, b) => {
      const priorityDelta = getLeadRowPriority(b) - getLeadRowPriority(a);
      if (priorityDelta !== 0) {
        return priorityDelta;
      }

      const aAnalyzed =
        a.score_kind === "final_score" || a.analysis_state === "analyzed" ? 1 : 0;
      const bAnalyzed =
        b.score_kind === "final_score" || b.analysis_state === "analyzed" ? 1 : 0;
      if (aAnalyzed !== bAnalyzed) {
        return bAnalyzed - aAnalyzed;
      }

      return (
        (b.updated_at || "").localeCompare(a.updated_at || "") ||
        (b.created_at || "").localeCompare(a.created_at || "") ||
        (a.id || "").localeCompare(b.id || "")
      );
    })[0] || null
  );
}

function findLeadByEntity(leads: Lead[], target: Lead | null | undefined) {
  return findBestLeadByEntity(leads, target);
}

function findProcessedDetailsByEntity(
  detailsMap: Record<string, ProcessedLeadDetails> | undefined,
  leads: Lead[],
  target: Lead | null | undefined
) {
  if (!target || !detailsMap) {
    return undefined;
  }

  if (detailsMap[target.id]) {
    return detailsMap[target.id];
  }

  const matchedLead = findLeadByEntity(leads, target);
  if (matchedLead?.id && detailsMap[matchedLead.id]) {
    return detailsMap[matchedLead.id];
  }

  return undefined;
}

function getExactProcessedDetailsForLead(
  detailsMap: Record<string, ProcessedLeadDetails> | undefined,
  target: Lead | null | undefined
) {
  if (!target?.id || !detailsMap) {
    return undefined;
  }

  return detailsMap[target.id];
}

function getProcessedDetailsForLead(
  detailsMap: Record<string, ProcessedLeadDetails> | undefined,
  leads: Lead[],
  target: Lead | null | undefined
) {
  const exactMatch = getExactProcessedDetailsForLead(detailsMap, target);
  if (exactMatch) {
    return exactMatch;
  }

  if (!target?.id) {
    return findProcessedDetailsByEntity(detailsMap, leads, target) || undefined;
  }

  return undefined;
}

function replaceLeadRow(existing: Lead[], previousLeadId: string, incoming: Lead) {
  const filtered = existing.filter(
    (lead) =>
      lead.id !== previousLeadId &&
      lead.id !== incoming.id &&
      !isSameLeadEntity(lead, incoming)
  );
  return dedupeLeadRows([...filtered, incoming]);
}

function replaceProcessedLeadDetails(
  existing: Record<string, ProcessedLeadDetails> | undefined,
  previousLeadId: string,
  nextLeadId: string
) {
  const current = { ...(existing || {}) };
  const previousDetails = current[previousLeadId];
  if (previousLeadId !== nextLeadId) {
    delete current[previousLeadId];
  }
  if (previousDetails) {
    current[nextLeadId] = {
      ...(current[nextLeadId] || {}),
      ...previousDetails,
    };
  }
  return current;
}

function mergeProcessedLeadDetailsRecords(
  existing: ProcessedLeadDetails | null | undefined,
  incoming: ProcessedLeadDetails | null | undefined
) {
  if (!existing && !incoming) {
    return null;
  }

  if (!existing) {
    return incoming ? { ...incoming } : null;
  }

  if (!incoming) {
    return { ...existing };
  }

  const parseUpdatedAt = (value: string | null | undefined) => {
    const timestamp = Date.parse(String(value || ""));
    return Number.isFinite(timestamp) ? timestamp : Number.NEGATIVE_INFINITY;
  };

  const getStateRank = (value: string | null | undefined) => {
    switch (value) {
      case "analyzed":
        return 4;
      case "analyzing":
        return 3;
      case "failed":
        return 2;
      case "preview":
        return 1;
      default:
        return 0;
    }
  };

  const incomingUpdatedAt = parseUpdatedAt(incoming.analysis_updated_at);
  const existingUpdatedAt = parseUpdatedAt(existing.analysis_updated_at);
  const incomingStateRank = getStateRank(incoming.analysis_state);
  const existingStateRank = getStateRank(existing.analysis_state);
  const incomingFactsCount = Object.keys(incoming.signal_facts || {}).length;
  const existingFactsCount = Object.keys(existing.signal_facts || {}).length;
  const preserveExistingAnalyzed =
    existing.analysis_state === "analyzed" &&
    incoming.analysis_state === "failed" &&
    existingFactsCount >= incomingFactsCount;
  const incomingIsPrimary =
    (!preserveExistingAnalyzed && incomingUpdatedAt > existingUpdatedAt) ||
    (incomingUpdatedAt === existingUpdatedAt &&
      (incomingStateRank > existingStateRank ||
        (incomingStateRank === existingStateRank &&
          incomingFactsCount >= existingFactsCount)));
  const primary = incomingIsPrimary ? incoming : existing;
  const secondary = incomingIsPrimary ? existing : incoming;

  return {
    ...secondary,
    ...primary,
    enrichment: {
      ...(secondary.enrichment || {}),
      ...(primary.enrichment || {}),
    },
    intent: {
      ...(secondary.intent || {}),
      ...(primary.intent || {}),
    },
    proof: {
      ...(secondary.proof || {}),
      ...(primary.proof || {}),
    },
    scoring: {
      ...(secondary.scoring || {}),
      ...(primary.scoring || {}),
    },
    signal_facts: primary.signal_facts ?? secondary.signal_facts,
    analysis_bundle: primary.analysis_bundle ?? secondary.analysis_bundle,
    analysis_state: primary.analysis_state ?? secondary.analysis_state,
    analysis_updated_at: primary.analysis_updated_at ?? secondary.analysis_updated_at,
    signals_version: primary.signals_version ?? secondary.signals_version,
    error: primary.error ?? secondary.error,
    outreach: primary.outreach ?? secondary.outreach ?? [],
  };
}

function mergeProcessedDetailsMapRecords(
  existing: Record<string, ProcessedLeadDetails> | undefined,
  incoming: Record<string, ProcessedLeadDetails> | undefined
) {
  const merged: Record<string, ProcessedLeadDetails> = {
    ...(existing || {}),
  };

  for (const [leadId, details] of Object.entries(incoming || {})) {
    const nextDetails = mergeProcessedLeadDetailsRecords(merged[leadId], details);
    if (nextDetails) {
      merged[leadId] = nextDetails;
    }
  }

  return merged;
}

function buildQueuedProcessedDetails(
  existing: ProcessedLeadDetails | null | undefined,
  analysisUpdatedAt: string | null | undefined,
  clearPreviousTruth: boolean
) {
  if (!clearPreviousTruth) {
    return {
      ...(existing || {}),
      analysis_state: "analyzing",
      analysis_updated_at: analysisUpdatedAt || null,
    } as ProcessedLeadDetails;
  }

  return {
    enrichment: {},
    error: undefined,
    intent: {},
    proof: {},
    scoring: {},
    outreach: [],
    signal_facts: undefined,
    analysis_bundle: undefined,
    analysis_state: "analyzing",
    analysis_updated_at: analysisUpdatedAt || undefined,
    signals_version: undefined,
  } as ProcessedLeadDetails;
}

function collectProcessedDetailsForLeadEntity(
  detailsMap: Record<string, ProcessedLeadDetails> | undefined,
  leads: Lead[],
  target: Lead | null | undefined
) {
  if (!target || !detailsMap) {
    return undefined;
  }

  let mergedDetails: ProcessedLeadDetails | null =
    target.id && detailsMap[target.id] ? { ...detailsMap[target.id] } : null;
  const matchedIds = new Set<string>(target.id ? [target.id] : []);

  for (const lead of leads) {
    if (!lead?.id || matchedIds.has(lead.id) || !isSameLeadEntity(lead, target)) {
      continue;
    }

    matchedIds.add(lead.id);
    const candidateDetails = detailsMap[lead.id];
    if (!candidateDetails) {
      continue;
    }

    mergedDetails = mergeProcessedLeadDetailsRecords(mergedDetails, candidateDetails);
  }

  return mergedDetails || undefined;
}

function canonicalizeLeadListState({
  leads,
  processedDetails,
  selectedLeadId,
}: {
  leads: Lead[];
  processedDetails?: Record<string, ProcessedLeadDetails>;
  selectedLeadId?: string | null;
}) {
  const sanitizedLeads = sanitizeLeadRows(leads);
  const canonicalLeads = dedupeLeadRows(sanitizedLeads);
  const canonicalProcessedDetails: Record<string, ProcessedLeadDetails> = {};

  for (const lead of canonicalLeads) {
    const exactDetails = getExactProcessedDetailsForLead(processedDetails, lead);

    if (exactDetails && Object.keys(exactDetails).length > 0) {
      canonicalProcessedDetails[lead.id] = exactDetails;
    }
  }

  const hydratedLeads = dedupeLeadRows(
    canonicalLeads.map(
      (lead) =>
        hydrateLeadFromStoredAnalysis(
          lead,
          getProcessedDetailsForLead(canonicalProcessedDetails, canonicalLeads, lead)
        ) || lead
    )
  );
  const resolvedSelectedLeadId = resolveSelectedLeadId(
    selectedLeadId ?? null,
    hydratedLeads,
    sanitizedLeads
  );

  return {
    leads: hydratedLeads,
    processedDetails: canonicalProcessedDetails,
    selectedLeadId: resolvedSelectedLeadId,
  };
}

function serializeLeadListPayload(
  leads: Lead[],
  metadata?: Pick<
    LeadListMetadata,
    | "autoAnalyzeCompletedToken"
    | "autoAnalyzeEnabled"
    | "filter"
    | "processedDetails"
    | "selectedLeadId"
    | "sortBy"
    | "sortOrder"
  >
) {
  return JSON.stringify({
    autoAnalyzeCompletedToken: metadata?.autoAnalyzeCompletedToken || null,
    autoAnalyzeEnabled: metadata?.autoAnalyzeEnabled ?? true,
    filter: metadata?.filter || "",
    leads,
    processedDetails: metadata?.processedDetails || {},
    selectedLeadId: metadata?.selectedLeadId || null,
    sortBy: metadata?.sortBy || "score",
    sortOrder: metadata?.sortOrder || "desc",
  });
}

const LEAD_LIST_SNAPSHOT_PREFIX = "zrai:lead-list-snapshot:";
const AUTO_ANALYZE_MAX_LEADS = 10;

function getLeadListSnapshotKey(documentId: string | null | undefined) {
  if (!documentId || documentId === "init") {
    return null;
  }

  return `${LEAD_LIST_SNAPSHOT_PREFIX}${documentId}`;
}

function persistLeadListDocument(
  artifact: { documentId?: string | null; title?: string | null; kind?: string | null } | null | undefined,
  nextContent: string
) {
  const snapshotKey = getLeadListSnapshotKey(artifact?.documentId);
  if (snapshotKey) {
    try {
      window.localStorage.setItem(snapshotKey, nextContent);
    } catch {}
  }

  if (!artifact?.documentId || artifact.documentId === "init") {
    return;
  }

  void fetch(`/api/document?id=${artifact.documentId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      title: artifact.title || "Lead List",
      content: nextContent,
      kind: artifact.kind || "lead-list",
    }),
  }).catch(() => {});
}

function getLeadAnalysisStrength(
  leads: Lead[],
  processedDetails: Record<string, ProcessedLeadDetails> | undefined
) {
  const analyzedLeadCount = leads.filter(
    (lead) => lead.score_kind === "final_score" || lead.analysis_state === "analyzed"
  ).length;
  const analyzedDetailsCount = Object.values(processedDetails || {}).filter(
    (details) => details?.analysis_state === "analyzed"
  ).length;
  const detailCount = Object.keys(processedDetails || {}).length;

  return analyzedLeadCount * 1000 + analyzedDetailsCount * 100 + detailCount;
}

function shouldPreferLeadListSnapshot(
  candidate: ReturnType<typeof parseLeadListPayload>,
  current: ReturnType<typeof parseLeadListPayload>
) {
  const candidateStrength = getLeadAnalysisStrength(
    candidate.leads,
    candidate.processedDetails
  );
  const currentStrength = getLeadAnalysisStrength(
    current.leads,
    current.processedDetails
  );

  if (candidateStrength !== currentStrength) {
    return candidateStrength > currentStrength;
  }

  const candidateLeadCount = dedupeLeadRows(candidate.leads).length;
  const currentLeadCount = dedupeLeadRows(current.leads).length;

  return candidateLeadCount > 0 && candidateLeadCount < currentLeadCount;
}

function getStableLeadKey(lead: Lead, index: number) {
  return getCanonicalLeadEntityKey(lead) || lead.id || lead.company_name || `lead-${index}`;
}

function getStableContactKey(leadId: string, contact: Lead["contacts"][number], index: number) {
  return (
    contact.id ||
    `${leadId}-${contact.email || contact.phone || contact.name || "contact"}-${index}`
  );
}

function filterLeads(leads: Lead[], filter: string) {
  if (!filter) {
    return leads;
  }

  const normalizedFilter = filter.toLowerCase();

  return leads.filter(
    (lead) =>
      getLeadDisplayName(lead).toLowerCase().includes(normalizedFilter) ||
      String(lead.business_name || "").toLowerCase().includes(normalizedFilter) ||
      String(lead.company_name || "").toLowerCase().includes(normalizedFilter) ||
      String(lead.domain || "").toLowerCase().includes(normalizedFilter) ||
      getLeadWebsiteHostValue(lead).toLowerCase().includes(normalizedFilter) ||
      lead.niche.toLowerCase().includes(normalizedFilter) ||
      getLeadSource(lead).toLowerCase().includes(normalizedFilter) ||
      getLeadFit(lead).toLowerCase().includes(normalizedFilter)
  );
}

function sortLeads(
  leads: Lead[],
  sortBy: string,
  sortOrder: "asc" | "desc"
) {
  return [...leads].sort((a, b) => {
    if (sortBy === "score") {
      const aFinal = a.score_kind === "final_score" ? 1 : 0;
      const bFinal = b.score_kind === "final_score" ? 1 : 0;

      if (aFinal !== bFinal) {
        return sortOrder === "asc" ? aFinal - bFinal : bFinal - aFinal;
      }

      const aScore = a.score ?? -1;
      const bScore = b.score ?? -1;
      if (aScore !== bScore) {
        return sortOrder === "asc" ? aScore - bScore : bScore - aScore;
      }

      const aName = getLeadDisplayName(a).toLowerCase();
      const bName = getLeadDisplayName(b).toLowerCase();
      if (aName !== bName) {
        return aName.localeCompare(bName);
      }

      return (a.id || "").localeCompare(b.id || "");
    }

    let aVal: unknown = a[sortBy as keyof Lead];
    let bVal: unknown = b[sortBy as keyof Lead];

    if (typeof aVal === "string") {
      aVal = aVal.toLowerCase();
    }
    if (typeof bVal === "string") {
      bVal = bVal.toLowerCase();
    }

    if (aVal == null && bVal == null) {
      return 0;
    }
    if (aVal == null) {
      return sortOrder === "asc" ? -1 : 1;
    }
    if (bVal == null) {
      return sortOrder === "asc" ? 1 : -1;
    }
    if (aVal < bVal) {
      return sortOrder === "asc" ? -1 : 1;
    }
    if (aVal > bVal) {
      return sortOrder === "asc" ? 1 : -1;
    }
    const aName = getLeadDisplayName(a).toLowerCase();
    const bName = getLeadDisplayName(b).toLowerCase();
    if (aName !== bName) {
      return aName.localeCompare(bName);
    }
    return (a.id || "").localeCompare(b.id || "");
  });
}

function LeadRow({ lead, onClick }: { lead: Lead; onClick: () => void }) {
  const displayName = getLeadDisplayName(lead);
  const secondaryIdentity = getLeadWebsiteHostValue(lead) || normalizeLeadDomainValue(lead.domain);
  const scoreColor =
    (lead.score || 0) >= 80
      ? "text-green-600"
      : (lead.score || 0) >= 60
        ? "text-yellow-600"
        : "text-red-600";

  return (
    <tr
      className="cursor-pointer border-zinc-200 border-b hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
      onClick={onClick}
    >
      <td className="p-3">
        <div className="font-medium">{displayName}</div>
        <div className="text-xs text-zinc-500">{secondaryIdentity}</div>
        {getLeadSummary(lead) && (
          <div className="mt-1 text-xs text-zinc-500">
            {getLeadSummary(lead)}
          </div>
        )}
      </td>
      <td className="p-3 text-sm">{getLeadFit(lead)}</td>
      <td className="p-3 text-sm text-zinc-500">{getLeadSource(lead)}</td>
      <td className="p-3 text-sm">{lead.geo}</td>
      <td className={`p-3 font-bold text-sm ${scoreColor}`}>
        <div>{lead.score ?? "-"}</div>
        <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500">
          {getScoreLabel(lead)}
        </div>
      </td>
      <td className="p-3">
        <span className="rounded-full bg-zinc-100 px-2 py-1 text-xs dark:bg-zinc-800">
          {formatLeadStatus(lead.status)}
        </span>
        <div className="mt-1 text-[10px] uppercase tracking-[0.18em] text-zinc-500">
          {getAnalysisLabel(lead)}
        </div>
      </td>
      <td className="p-3 text-sm text-zinc-500">
        {lead.contacts?.length || 0}
      </td>
    </tr>
  );
}

function parseLeads(content: string): Lead[] {
  return parseLeadListPayload(content).leads;
}

function parseLeadListPayload(content: string): {
  filter: string;
  leads: Lead[];
  processedDetails: Record<string, ProcessedLeadDetails>;
  autoAnalyzeCompletedToken: string | null;
  autoAnalyzeEnabled: boolean;
  selectedLeadId: string | null;
  sortBy: string;
  sortOrder: "asc" | "desc";
} {
  if (!content) {
    return {
      filter: "",
      leads: [],
      processedDetails: {},
      autoAnalyzeCompletedToken: null,
      autoAnalyzeEnabled: true,
      selectedLeadId: null,
      sortBy: "score",
      sortOrder: "desc",
    };
  }

  try {
    const parsed = JSON.parse(content) as Lead[] | LeadListPayload;
    const payload = Array.isArray(parsed) ? ({ leads: parsed } satisfies LeadListPayload) : parsed;
    const canonical = canonicalizeLeadListState({
      leads: dedupeLeadRows(sanitizeLeadRows(payload.leads || [])),
      processedDetails: payload.processedDetails || payload.processed_details || {},
      selectedLeadId: payload.selectedLeadId || null,
    });

    return {
      filter: payload.filter || "",
      leads: canonical.leads,
      processedDetails: canonical.processedDetails,
      autoAnalyzeCompletedToken: payload.autoAnalyzeCompletedToken || null,
      autoAnalyzeEnabled: payload.autoAnalyzeEnabled ?? true,
      selectedLeadId: canonical.selectedLeadId,
      sortBy: payload.sortBy || "score",
      sortOrder: payload.sortOrder === "asc" ? "asc" : "desc",
    };
  } catch {
    return {
      filter: "",
      leads: [],
      processedDetails: {},
      autoAnalyzeCompletedToken: null,
      autoAnalyzeEnabled: true,
      selectedLeadId: null,
      sortBy: "score",
      sortOrder: "desc",
    };
  }
}

function LeadListContent({
  content,
  metadata,
  setMetadata,
}: {
  content: string;
  metadata: LeadListMetadata;
  setMetadata: (fn: (prev: LeadListMetadata) => LeadListMetadata) => void;
}) {
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [selectedLeadLive, setSelectedLeadLive] = useState<Lead | null>(null);
  const [selectedLeadLiveDetails, setSelectedLeadLiveDetails] =
    useState<ProcessedLeadDetails | null>(null);
  const [processingIds, setProcessingIds] = useState<string[]>([]);
  const [isRefreshingTruth, setIsRefreshingTruth] = useState(false);
  const processControllersRef = useRef<Record<string, AbortController>>({});
  const founderIntelCacheRef = useRef<Record<string, FounderIntelPayload>>({});
  const leadsRef = useRef<Lead[]>([]);
  const processedDetailsRef = useRef<Record<string, ProcessedLeadDetails>>({});
  const selectedLeadIdRef = useRef<string | null>(null);
  const persistTimeoutRef = useRef<number | null>(null);
  const snapshotRestoreRef = useRef<string | null>(null);
  const truthRecoveryRef = useRef<string | null>(null);
  const autoAnalyzeRunRef = useRef<string | null>(null);
  const { artifact, setArtifact } = useArtifact();

  const contentPayload = parseLeadListPayload(content);
  const contentLeads = contentPayload.leads;
  const metadataLeads = dedupeLeadRows(sanitizeLeadRows(metadata?.leads || []));
  const mergedProcessedDetails = mergeProcessedDetailsMapRecords(
    contentPayload.processedDetails || {},
    metadata?.processedDetails || {}
  );
  const mergedRawLeads = sanitizeLeadRows(
    mergeLeadRows(contentLeads, metadataLeads)
  );
  const canonicalState = canonicalizeLeadListState({
    leads: mergedRawLeads,
    processedDetails: mergedProcessedDetails,
    selectedLeadId: metadata?.selectedLeadId || contentPayload.selectedLeadId || null,
  });
  const leads = canonicalState.leads;
  const processedDetails = canonicalState.processedDetails;

  const filter = metadata?.filter || contentPayload.filter || "";
  const filteredLeads = filterLeads(leads, filter);

  const sortBy = metadata?.sortBy || contentPayload.sortBy || "score";
  const sortOrder = metadata?.sortOrder || contentPayload.sortOrder || "desc";
  const sortedLeads = sortLeads(filteredLeads, sortBy, sortOrder);
  const fallbackVisibleLead =
    metadata?.liveSelectedLead || selectedLeadLive || selectedLead || null;
  const displayLeads = sortedLeads.length
    ? sortedLeads
    : fallbackVisibleLead
      ? dedupeLeadRows([sanitizeLeadRecord(fallbackVisibleLead)])
      : [];
  const persistedSelectedLeadId = canonicalState.selectedLeadId || null;
  const autoAnalyzeEnabled =
    metadata?.autoAnalyzeEnabled ?? contentPayload.autoAnalyzeEnabled ?? true;
  const autoAnalyzeCompletedToken =
    metadata?.autoAnalyzeCompletedToken ||
    contentPayload.autoAnalyzeCompletedToken ||
    null;

  const queueLeadListDocumentSave = (nextContent: string) => {
    if (persistTimeoutRef.current) {
      window.clearTimeout(persistTimeoutRef.current);
      persistTimeoutRef.current = null;
    }

    persistLeadListDocument(artifact, nextContent);
  };

  useEffect(() => {
    leadsRef.current = leads;
  }, [leads]);

  useEffect(() => {
    processedDetailsRef.current = processedDetails || {};
  }, [processedDetails]);

  useEffect(() => {
    selectedLeadIdRef.current = persistedSelectedLeadId;
  }, [persistedSelectedLeadId]);

  useEffect(() => {
    if (!leads.length && fallbackVisibleLead) {
      syncLeadListState({
        nextLeads: [sanitizeLeadRecord(fallbackVisibleLead)],
        nextProcessedDetails: processedDetails,
        nextSelectedLeadId: fallbackVisibleLead.id,
      });
    }
  }, [fallbackVisibleLead, leads.length, processedDetails]);

  useEffect(() => {
    const snapshotKey = getLeadListSnapshotKey(artifact?.documentId);
    if (!snapshotKey) {
      return;
    }

    const restoreToken = `${artifact.documentId}:${content}`;
    if (snapshotRestoreRef.current === restoreToken) {
      return;
    }
    snapshotRestoreRef.current = restoreToken;

    let snapshotContent: string | null = null;
    try {
      snapshotContent = window.localStorage.getItem(snapshotKey);
    } catch {
      return;
    }

    if (!snapshotContent || snapshotContent === content) {
      return;
    }

    const currentPayload = parseLeadListPayload(content);
    const snapshotPayload = parseLeadListPayload(snapshotContent);

    if (!shouldPreferLeadListSnapshot(snapshotPayload, currentPayload)) {
      return;
    }

    const nextProcessedDetails = mergeProcessedDetailsMapRecords(
      mergeProcessedDetailsMapRecords(
        currentPayload.processedDetails || {},
        snapshotPayload.processedDetails || {}
      ),
      metadata?.processedDetails || {}
    );
    const mergedSnapshotLeads = mergeLeadRows(currentPayload.leads, snapshotPayload.leads);
    const canonicalSnapshotState = canonicalizeLeadListState({
      leads: mergedSnapshotLeads,
      processedDetails: nextProcessedDetails,
      selectedLeadId:
        metadata?.selectedLeadId ||
        snapshotPayload.selectedLeadId ||
        currentPayload.selectedLeadId ||
        null,
    });
    const nextContent = serializeLeadListPayload(canonicalSnapshotState.leads, {
      autoAnalyzeCompletedToken:
        metadata?.autoAnalyzeCompletedToken ||
        snapshotPayload.autoAnalyzeCompletedToken ||
        currentPayload.autoAnalyzeCompletedToken ||
        null,
      autoAnalyzeEnabled:
        metadata?.autoAnalyzeEnabled ??
        snapshotPayload.autoAnalyzeEnabled ??
        currentPayload.autoAnalyzeEnabled ??
        true,
      filter: metadata?.filter || snapshotPayload.filter || currentPayload.filter || "",
      processedDetails: canonicalSnapshotState.processedDetails,
      selectedLeadId: canonicalSnapshotState.selectedLeadId,
      sortBy: metadata?.sortBy || snapshotPayload.sortBy || currentPayload.sortBy || "score",
      sortOrder:
        metadata?.sortOrder || snapshotPayload.sortOrder || currentPayload.sortOrder || "desc",
    });

    setMetadata((prev: LeadListMetadata) => ({
      ...prev,
      leads: canonicalSnapshotState.leads,
      processedDetails: canonicalSnapshotState.processedDetails,
      selectedLeadId: canonicalSnapshotState.selectedLeadId,
      autoAnalyzeCompletedToken:
        prev.autoAnalyzeCompletedToken ||
        snapshotPayload.autoAnalyzeCompletedToken ||
        currentPayload.autoAnalyzeCompletedToken ||
        null,
      autoAnalyzeEnabled:
        prev.autoAnalyzeEnabled ??
        snapshotPayload.autoAnalyzeEnabled ??
        currentPayload.autoAnalyzeEnabled ??
        true,
      filter: prev.filter || snapshotPayload.filter || currentPayload.filter || "",
      sortBy: prev.sortBy || snapshotPayload.sortBy || currentPayload.sortBy || "score",
      sortOrder:
        prev.sortOrder || snapshotPayload.sortOrder || currentPayload.sortOrder || "desc",
    }));
    setArtifact((draft) => ({
      ...draft,
      content: nextContent,
    }));
    queueLeadListDocumentSave(nextContent);
  }, [
    artifact?.documentId,
    content,
    metadata?.filter,
    metadata?.leads,
    metadata?.processedDetails,
    metadata?.selectedLeadId,
    metadata?.autoAnalyzeCompletedToken,
    metadata?.autoAnalyzeEnabled,
    metadata?.sortBy,
    metadata?.sortOrder,
    setArtifact,
    setMetadata,
  ]);

  const persistLeadListContent = ({
    nextAutoAnalyzeCompletedToken,
    nextAutoAnalyzeEnabled,
    nextFilter,
    nextLeads,
    nextProcessedDetails,
    nextSelectedLeadId,
    nextSortBy,
    nextSortOrder,
  }: {
    nextAutoAnalyzeCompletedToken?: string | null;
    nextAutoAnalyzeEnabled?: boolean;
    nextFilter?: string;
    nextLeads?: Lead[];
    nextProcessedDetails?: Record<string, ProcessedLeadDetails>;
    nextSelectedLeadId?: string | null;
    nextSortBy?: string;
    nextSortOrder?: "asc" | "desc";
  }) => {
    const canonical = canonicalizeLeadListState({
      leads: nextLeads || leads,
      processedDetails: nextProcessedDetails ?? processedDetails ?? {},
      selectedLeadId:
        nextSelectedLeadId !== undefined ? nextSelectedLeadId : persistedSelectedLeadId,
    });
    const nextContent = serializeLeadListPayload(canonical.leads, {
      autoAnalyzeCompletedToken:
        nextAutoAnalyzeCompletedToken !== undefined
          ? nextAutoAnalyzeCompletedToken
          : autoAnalyzeCompletedToken,
      autoAnalyzeEnabled:
        nextAutoAnalyzeEnabled !== undefined
          ? nextAutoAnalyzeEnabled
          : autoAnalyzeEnabled,
      filter: nextFilter ?? filter,
      processedDetails: canonical.processedDetails,
      selectedLeadId: canonical.selectedLeadId,
      sortBy: nextSortBy ?? sortBy,
      sortOrder: nextSortOrder ?? sortOrder,
    });

    setArtifact((draft) => ({
      ...draft,
      content: nextContent,
    }));
    queueLeadListDocumentSave(nextContent);
  };

  useEffect(() => {
    const canonical = canonicalizeLeadListState({
      leads,
      processedDetails: processedDetails || {},
      selectedLeadId: persistedSelectedLeadId,
    });
    const nextContent = serializeLeadListPayload(canonical.leads, {
      autoAnalyzeCompletedToken,
      autoAnalyzeEnabled,
      filter,
      processedDetails: canonical.processedDetails,
      selectedLeadId: canonical.selectedLeadId,
      sortBy,
      sortOrder,
    });

    if (nextContent === content) {
      return;
    }

    setArtifact((draft) => ({
      ...draft,
      content: nextContent,
    }));
    queueLeadListDocumentSave(nextContent);
  }, [
    artifact.documentId,
    artifact.kind,
    artifact.title,
    autoAnalyzeCompletedToken,
    autoAnalyzeEnabled,
    content,
    filter,
    leads,
    persistedSelectedLeadId,
    processedDetails,
    setArtifact,
    sortBy,
    sortOrder,
  ]);

  useEffect(() => {
    return () => {
      if (persistTimeoutRef.current) {
        window.clearTimeout(persistTimeoutRef.current);
      }
    };
  }, []);

  const hydrateFounderIntel = async (
    baseLead: Lead,
    baseProcessedDetails: ProcessedLeadDetails | null | undefined
  ) => {
    if (!baseLead?.id || !needsFounderIntelligence(baseLead, baseProcessedDetails)) {
      return {
        lead: baseLead,
        processedDetails: baseProcessedDetails || null,
      };
    }

    try {
      const cachedFounderIntel = founderIntelCacheRef.current[baseLead.id];
      const founderIntel =
        cachedFounderIntel || (await fetchFounderIntelligence(baseLead));

      if (!cachedFounderIntel && Object.keys(founderIntel || {}).length > 0) {
        founderIntelCacheRef.current[baseLead.id] = founderIntel;
      }

      if (!founderIntel || Object.keys(founderIntel).length === 0) {
        return {
          lead: baseLead,
          processedDetails: baseProcessedDetails || null,
        };
      }

      const nextProcessedDetails = mergeFounderIntelligenceIntoProcessedDetails(
        baseProcessedDetails || null,
        founderIntel
      ) as ProcessedLeadDetails;

      return {
        lead: {
          ...baseLead,
          signal_facts: nextProcessedDetails?.signal_facts || baseLead.signal_facts,
        } as Lead,
        processedDetails: nextProcessedDetails,
      };
    } catch {
      return {
        lead: baseLead,
        processedDetails: baseProcessedDetails || null,
      };
    }
  };

  const syncLeadListState = ({
    nextLeads,
    nextProcessedDetails,
    nextSelectedLeadId,
  }: {
    nextLeads: Lead[];
    nextProcessedDetails?: Record<string, ProcessedLeadDetails>;
    nextSelectedLeadId?: string | null;
    }) => {
      setMetadata((prev: LeadListMetadata) => {
        const canonical = canonicalizeLeadListState({
          leads: nextLeads,
          processedDetails: nextProcessedDetails ?? prev.processedDetails ?? {},
          selectedLeadId:
            nextSelectedLeadId !== undefined
              ? nextSelectedLeadId
              : prev.selectedLeadId ?? contentPayload.selectedLeadId ?? null,
        });
        const updated = {
          ...prev,
          leads: canonical.leads,
          processedDetails: canonical.processedDetails,
          selectedLeadId: canonical.selectedLeadId,
        };

        persistLeadListContent({
          nextAutoAnalyzeCompletedToken: updated.autoAnalyzeCompletedToken,
          nextAutoAnalyzeEnabled: updated.autoAnalyzeEnabled,
          nextFilter: updated.filter,
          nextLeads: updated.leads,
          nextProcessedDetails: updated.processedDetails,
          nextSelectedLeadId: updated.selectedLeadId ?? null,
          nextSortBy: updated.sortBy,
          nextSortOrder: updated.sortOrder,
        });

      return updated;
    });
  };

  const buildProcessedDetailsFromPayload = (
    payloadData: Record<string, any> | null | undefined
  ): ProcessedLeadDetails | null => {
    if (!payloadData) {
      return null;
    }

    const baseProcessedDetails = payloadData.processed_details || {};
    const nextProcessedDetails = {
      ...baseProcessedDetails,
      signal_facts: payloadData.signal_facts || baseProcessedDetails?.signal_facts || null,
      analysis_bundle: payloadData.analysis_bundle || baseProcessedDetails?.analysis_bundle || null,
      analysis_state: payloadData.analysis_state || baseProcessedDetails?.analysis_state || null,
      analysis_updated_at:
        payloadData.analysis_updated_at || baseProcessedDetails?.analysis_updated_at || null,
      signals_version: payloadData.signals_version || baseProcessedDetails?.signals_version || null,
    } as ProcessedLeadDetails;

    return Object.keys(nextProcessedDetails).length > 0 ? nextProcessedDetails : null;
  };

  useEffect(() => {
    const documentId = artifact?.documentId;
    if (!documentId || documentId === "init" || !leads.length) {
      return;
    }

    const hasSavedAnalysis = leads.some(
      (lead) => lead.score_kind === "final_score" || lead.analysis_state === "analyzed"
    );

    if (hasSavedAnalysis) {
      return;
    }

    const recoveryToken = `${documentId}:${content}`;
    if (truthRecoveryRef.current === recoveryToken) {
      return;
    }
    truthRecoveryRef.current = recoveryToken;

    let cancelled = false;

    void (async () => {
      try {
        const recoveredLeads: Lead[] = [];
        const recoveredProcessedDetails: Record<string, ProcessedLeadDetails> = {};

        for (const rawLead of leads) {
          const persistedLead = isUuidLeadId(rawLead.id)
            ? rawLead
            : await ensurePersistedLead(rawLead);
          const response = await fetch(getZRAILeadByIdEndpoint(persistedLead.id));
          if (!response.ok) {
            continue;
          }

          const payload = await response.json();
          const payloadData = getPayloadData(payload) as Record<string, any>;
          if (!(payload?.success ?? true) || !payloadData?.lead) {
            continue;
          }

          const latestLead = payloadData.lead as Lead;
          const latestProcessedDetails = buildProcessedDetailsFromPayload(payloadData);
          const hydrated = await hydrateFounderIntel(latestLead, latestProcessedDetails);
          const hydratedState = getResolvedAnalysisState(
            hydrated.lead,
            hydrated.processedDetails
          );

          if (
            hydratedState !== "analyzed" &&
            hydrated.lead.score_kind !== "final_score" &&
            !hydrated.processedDetails
          ) {
            continue;
          }

          recoveredLeads.push(hydrated.lead);
          if (hydrated.processedDetails) {
            recoveredProcessedDetails[hydrated.lead.id] = hydrated.processedDetails;
          }
        }

        if (
          cancelled ||
          (!recoveredLeads.length && !Object.keys(recoveredProcessedDetails).length)
        ) {
          return;
        }

        const nextProcessedDetails = {
          ...(processedDetailsRef.current || {}),
          ...recoveredProcessedDetails,
        };
        const nextLeads = sanitizeLeadRows(
          mergeLeadRows(leadsRef.current, recoveredLeads).map(
            (lead) =>
              hydrateLeadFromStoredAnalysis(
                lead,
                getProcessedDetailsForLead(
                  nextProcessedDetails,
                  mergeLeadRows(leadsRef.current, recoveredLeads),
                  lead
                )
              ) || lead
          )
        );
        const nextSelectedLeadId = resolveSelectedLeadId(
          selectedLeadIdRef.current,
          nextLeads,
          [...leadsRef.current, ...recoveredLeads]
        );

        syncLeadListState({
          nextLeads,
          nextProcessedDetails,
          nextSelectedLeadId,
        });
      } catch {
        // Recovery is best-effort. Keep the list usable even if backend truth lookup fails.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [artifact?.documentId, content, leads, processedDetails]);

  useEffect(() => {
    if (!persistedSelectedLeadId) {
      if (selectedLead) {
        setSelectedLead(null);
        setSelectedLeadLive(null);
        setSelectedLeadLiveDetails(null);
      }
      return;
    }

    if (selectedLead?.id === persistedSelectedLeadId) {
      return;
    }

    const rehydratedLead = leads.find((lead) => lead.id === persistedSelectedLeadId);
    if (!rehydratedLead) {
      return;
    }

    setSelectedLead(rehydratedLead);
    setSelectedLeadLive(null);
    setSelectedLeadLiveDetails(null);
  }, [persistedSelectedLeadId, leads, selectedLead]);

  useEffect(() => {
    if (!selectedLead) {
      setSelectedLeadLive(null);
      setSelectedLeadLiveDetails(null);
      return;
    }

    const hasSelectedLead = leads.some((lead) => lead.id === selectedLead.id);
    if (!hasSelectedLead) {
      setSelectedLead(null);
      setSelectedLeadLive(null);
      setSelectedLeadLiveDetails(null);
    }
  }, [leads, selectedLead]);

  const handleSort = (column: string) => {
    const nextSortOrder =
      sortBy === column && sortOrder === "desc" ? "asc" : "desc";
    setMetadata((prev: LeadListMetadata) => ({
      ...prev,
      sortBy: column,
      sortOrder: nextSortOrder,
    }));
    persistLeadListContent({
      nextSortBy: column,
      nextSortOrder,
    });
  };

  const clearProcessing = (leadIds: string[]) => {
    for (const leadId of leadIds) {
      delete processControllersRef.current[leadId];
    }
    setProcessingIds((prev) => prev.filter((id) => !leadIds.includes(id)));
  };

  const remapProcessingIds = (mappings: Array<{ from: string; to: string }>) => {
    const validMappings = mappings.filter(
      ({ from, to }) => Boolean(from) && Boolean(to) && from !== to
    );
    if (!validMappings.length) {
      return;
    }

    for (const { from, to } of validMappings) {
      const controller = processControllersRef.current[from];
      if (controller && !processControllersRef.current[to]) {
        processControllersRef.current[to] = controller;
      }
      delete processControllersRef.current[from];
    }

    setProcessingIds((prev) => {
      const remapped = prev.map((id) => {
        const mapping = validMappings.find(({ from }) => from === id);
        return mapping?.to || id;
      });
      return Array.from(new Set(remapped));
    });
  };

  const stopProcessing = (leadIds?: string[]) => {
    const idsToStop = leadIds?.length ? leadIds : Object.keys(processControllersRef.current);
    const controllers = Array.from(
      new Set(
        idsToStop
          .map((leadId) => processControllersRef.current[leadId])
          .filter((controller): controller is AbortController => Boolean(controller))
      )
    );

    for (const controller of controllers) {
      controller.abort();
    }

    clearProcessing(idsToStop);
    toast.success(
      idsToStop.length === 1
        ? "Stopped the running lead process."
        : "Stopped all running lead processes."
    );
  };

  const processLeads = async (
    leadIds: string[],
    options?: {
      includeOutreach?: boolean;
      forceRefresh?: boolean;
      successMessage?: string;
      emptyMessage?: string;
    }
  ) => {
    if (leadIds.length === 0) {
      return false;
    }

    const freshLeadIds = leadIds.filter((leadId) => !processingIds.includes(leadId));
    if (freshLeadIds.length === 0) {
      return false;
    }

    const controller = new AbortController();
    for (const leadId of freshLeadIds) {
      processControllersRef.current[leadId] = controller;
    }

    setProcessingIds((prev) => Array.from(new Set([...prev, ...freshLeadIds])));

    let activeLeadIds = [...freshLeadIds];
    let workingLeadRows = leadsRef.current;
    let workingProcessedDetails = processedDetailsRef.current;
    let workingSelectedLeadId = selectedLeadIdRef.current;

    try {
      const persistedLeadMap = new Map<string, Lead>();
      let nextLeadRows = workingLeadRows;
      let nextProcessedDetails = workingProcessedDetails;
      let nextSelectedLeadId = workingSelectedLeadId;

      for (const leadId of freshLeadIds) {
        const rawLead = workingLeadRows.find((candidate) => candidate.id === leadId);
        if (!rawLead) {
          continue;
        }

        if (isUuidLeadId(rawLead.id)) {
          persistedLeadMap.set(leadId, rawLead);
          continue;
        }

        const importedLead = await ensurePersistedLead(rawLead);
        persistedLeadMap.set(leadId, importedLead);
        nextLeadRows = replaceLeadRow(nextLeadRows, rawLead.id, importedLead);
        nextProcessedDetails = replaceProcessedLeadDetails(
          nextProcessedDetails,
          rawLead.id,
          importedLead.id
        );
        if (nextSelectedLeadId === rawLead.id) {
          nextSelectedLeadId = importedLead.id;
        }
      }

      if (
        nextLeadRows !== workingLeadRows ||
        nextProcessedDetails !== workingProcessedDetails ||
        nextSelectedLeadId !== workingSelectedLeadId
      ) {
        syncLeadListState({
          nextLeads: nextLeadRows,
          nextProcessedDetails,
          nextSelectedLeadId,
        });
      }

      workingLeadRows = nextLeadRows;
      workingProcessedDetails = nextProcessedDetails;
      workingSelectedLeadId = nextSelectedLeadId ?? null;

      const remappedLeadIds = Array.from(
        new Set(freshLeadIds.map((leadId) => persistedLeadMap.get(leadId)?.id || leadId))
      );
      remapProcessingIds(
        freshLeadIds.map((leadId, index) => ({
          from: leadId,
          to: persistedLeadMap.get(leadId)?.id || leadId,
        }))
      );
      activeLeadIds = remappedLeadIds;

      const response = await fetch(ZRAI_ENDPOINTS.processLeads, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        signal: controller.signal,
        body: JSON.stringify({
          lead_ids: activeLeadIds,
          include_outreach: options?.includeOutreach ?? true,
          force_refresh: options?.forceRefresh ?? false,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "Processing selected leads failed");
      }

      const payload = getPayloadData((await response.json()) as {
        processed?: ProcessedLeadResponseItem[];
      });
      const processedItems = payload.processed || [];
      const processedLeads = processedItems
        .filter((item: ProcessedLeadResponseItem) => item.success && item.lead)
        .map((item: ProcessedLeadResponseItem) => item.lead as Lead);
      const processedDetailEntries = processedItems
        .filter((item: ProcessedLeadResponseItem) => item.success && item.lead)
        .map((item: ProcessedLeadResponseItem) => [
          item.lead!.id,
          {
            enrichment: item.enrichment || {},
            intent: item.intent || {},
            proof: item.proof || {},
            outreach: item.outreach || [],
            scoring: item.scoring || {},
            signal_facts: item.signal_facts,
            analysis_bundle: item.analysis_bundle,
            analysis_state: item.analysis_state,
            analysis_updated_at: item.analysis_updated_at,
            signals_version: item.signals_version,
            error: undefined,
          } satisfies ProcessedLeadDetails,
        ] as const);
      const failedDetailEntries = processedItems
        .filter((item: ProcessedLeadResponseItem) => !item.success)
        .map((item: ProcessedLeadResponseItem) => [
          item.lead_id,
          {
            ...(workingProcessedDetails?.[item.lead_id] || {}),
            analysis_state: "failed",
            analysis_updated_at: new Date().toISOString(),
            error: item.error || "Lead analysis failed",
          } satisfies ProcessedLeadDetails,
        ] as const);

      const mergedLeads = dedupeLeadRows(mergeLeadRows(workingLeadRows, processedLeads));
      const mergedDetails = mergeProcessedDetailsMapRecords(
        mergeProcessedDetailsMapRecords(
          workingProcessedDetails,
          Object.fromEntries(processedDetailEntries)
        ),
        Object.fromEntries(failedDetailEntries)
      );
      const resolvedSelectedLeadId = selectedLead
        ? resolveSelectedLeadId(
            selectedLead.id,
            mergedLeads,
            [...workingLeadRows, ...processedLeads]
          )
        : workingSelectedLeadId;
      syncLeadListState({
        nextLeads: mergedLeads,
        nextProcessedDetails: mergedDetails,
        nextSelectedLeadId: resolvedSelectedLeadId,
      });

      if (selectedLead && resolvedSelectedLeadId) {
        const updatedLead = mergedLeads.find((lead) => lead.id === resolvedSelectedLeadId);
        if (updatedLead) {
          setSelectedLead(updatedLead);
          setSelectedLeadLive(updatedLead);
          setSelectedLeadLiveDetails(mergedDetails[updatedLead.id] || null);
        }
      }

      if (processedLeads.length === 0) {
        toast.error(options?.emptyMessage || "No leads were processed successfully.");
        return false;
      }

      toast.success(
        options?.successMessage ||
          `Processed ${processedLeads.length} lead${processedLeads.length === 1 ? "" : "s"} through enrichment, intent, proof, and scoring.`
      );
      return true;
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        toast.success("Lead processing stopped.");
        return false;
      }
      toast.error(error instanceof Error ? error.message : "Lead processing failed");
      return false;
    } finally {
      clearProcessing(activeLeadIds);
    }
  };

  useEffect(() => {
    if (!autoAnalyzeEnabled || !displayLeads.length || processingIds.length) {
      return;
    }

    const visibleLeads = dedupeLeadRows(displayLeads);
    const preferredLead = visibleLeads[0] || leads[0];
    if (!persistedSelectedLeadId && preferredLead) {
      selectedLeadIdRef.current = preferredLead.id;
      setSelectedLead(preferredLead);
      setSelectedLeadLive(null);
      setSelectedLeadLiveDetails(null);
      setMetadata((prev: LeadListMetadata) => ({
        ...prev,
        selectedLeadId: preferredLead.id,
        liveSelectedLead: null,
        liveSelectedLeadDetails: null,
      }));
      persistLeadListContent({
        nextSelectedLeadId: preferredLead.id,
      });
    }

    const candidates = visibleLeads
      .filter(
        (lead) =>
          !isTerminalAnalysisState(
            lead,
            getProcessedDetailsForLead(processedDetails, leads, lead)
          )
      )
      .slice(0, AUTO_ANALYZE_MAX_LEADS);

    if (!candidates.length) {
      return;
    }

    const token = `${artifact?.documentId || "draft"}:${candidates
      .map((lead) => lead.id)
      .join("|")}`;
    if (autoAnalyzeRunRef.current === token || autoAnalyzeCompletedToken === token) {
      return;
    }
    autoAnalyzeRunRef.current = token;

    void processLeads(
      candidates.map((lead) => lead.id),
      {
        includeOutreach: false,
        forceRefresh: false,
        successMessage: `Auto-analyzed ${candidates.length} lead${candidates.length === 1 ? "" : "s"} for the inspector.`,
        emptyMessage: "Auto-analysis did not finish any leads yet. Use Analyze visible to retry.",
      }
    ).then((completed) => {
      if (!completed) {
        return;
      }
      setMetadata((prev: LeadListMetadata) => ({
        ...prev,
        autoAnalyzeCompletedToken: token,
      }));
      persistLeadListContent({
        nextAutoAnalyzeCompletedToken: token,
      });
    });
  }, [
    artifact?.documentId,
    autoAnalyzeCompletedToken,
    autoAnalyzeEnabled,
    displayLeads,
    leads,
    persistedSelectedLeadId,
    processedDetails,
    processingIds.length,
    setMetadata,
  ]);

  useEffect(() => {
    if (!processingIds.length) {
      return;
    }

    const completedIds = processingIds.filter((leadId) => {
      const rowLead =
        leads.find((candidate) => candidate.id === leadId) ||
        (selectedLead?.id === leadId ? selectedLead : null) ||
        (selectedLeadLive?.id === leadId ? selectedLeadLive : null) ||
        (metadata?.liveSelectedLead?.id === leadId ? metadata.liveSelectedLead : null);
      const rowDetails =
        processedDetails?.[leadId] ||
        (selectedLeadLive?.id === leadId ? selectedLeadLiveDetails : null) ||
        (metadata?.liveSelectedLead?.id === leadId ? metadata.liveSelectedLeadDetails : null);

      return isTerminalAnalysisState(rowLead, rowDetails);
    });

    if (completedIds.length) {
      clearProcessing(completedIds);
    }
  }, [
    processingIds,
    leads,
    processedDetails,
    selectedLead,
    selectedLeadLive,
    selectedLeadLiveDetails,
    metadata?.liveSelectedLead,
    metadata?.liveSelectedLeadDetails,
  ]);

  const refreshSelectedLeadTruth = async () => {
    if (!selectedLead?.id) {
      return;
    }

    setIsRefreshingTruth(true);
    try {
      await analyzeSelectedLead(true);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Lead truth refresh failed");
    } finally {
      setIsRefreshingTruth(false);
    }
  };

  const pollLeadAnalysisCompletion = async (leadId: string) => {
    for (let attempt = 0; attempt < 45; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 4000));

      const response = await fetch(getZRAILeadByIdEndpoint(leadId));
      if (!response.ok) {
        continue;
      }

      const payload = await response.json();
      const payloadData = getPayloadData(payload);
      const latestLead = payloadData?.lead as Lead | undefined;
      const nextAnalysisState =
        payloadData?.analysis_state ||
        payloadData?.processed_details?.analysis_state ||
        latestLead?.analysis_state;

      if (!latestLead || !nextAnalysisState) {
        continue;
      }

      if (nextAnalysisState === "failed") {
        throw new Error("Lead analysis failed in the backend.");
      }

      if (nextAnalysisState !== "analyzed") {
        continue;
      }

      const latestProcessedDetailsRaw = payloadData.processed_details
        ? ({
            ...(payloadData.processed_details || {}),
            signal_facts: payloadData.signal_facts || payloadData.processed_details?.signal_facts || null,
            analysis_bundle: payloadData.analysis_bundle || payloadData.processed_details?.analysis_bundle || null,
            analysis_state: payloadData.analysis_state || payloadData.processed_details?.analysis_state || null,
            analysis_updated_at:
              payloadData.analysis_updated_at || payloadData.processed_details?.analysis_updated_at || null,
            signals_version: payloadData.signals_version || payloadData.processed_details?.signals_version || null,
          } as ProcessedLeadDetails)
        : null;
      const hydrated = await hydrateFounderIntel(latestLead, latestProcessedDetailsRaw);

      const baseLeads = leadsRef.current;
      const baseProcessedDetails = processedDetailsRef.current;
      const mergedLeads = dedupeLeadRows(mergeLeadRows(baseLeads, [hydrated.lead]));
      const resolvedSelectedLeadId = resolveSelectedLeadId(
        leadId,
        mergedLeads,
        [...baseLeads, hydrated.lead]
      );
      syncLeadListState({
        nextLeads: mergedLeads,
        nextProcessedDetails: hydrated.processedDetails
          ? {
              ...baseProcessedDetails,
              [leadId]: hydrated.processedDetails,
            }
          : baseProcessedDetails,
        nextSelectedLeadId: resolvedSelectedLeadId,
      });
      setSelectedLead(
        mergedLeads.find((lead) => lead.id === resolvedSelectedLeadId) || hydrated.lead
      );
      setSelectedLeadLive(hydrated.lead);
      setSelectedLeadLiveDetails(hydrated.processedDetails);
      setMetadata((prev: LeadListMetadata) => ({
        ...prev,
        liveSelectedLead: hydrated.lead,
        liveSelectedLeadDetails: hydrated.processedDetails,
      }));
      clearProcessing([leadId]);
      toast.success("Lead analyzed.");
      return;
    }

    clearProcessing([leadId]);
    toast.success("Analysis is still running. Use Refresh truth in a moment.");
  };

  const analyzeSelectedLead = async (forceRefresh: boolean = true) => {
    if (!selectedLead?.id) {
      return;
    }

    let activeLeadId = selectedLead.id;

    try {
      let workingLeadRows = leadsRef.current;
      let workingProcessedDetails = processedDetailsRef.current;
      const resolvedLead = isUuidLeadId(selectedLead.id)
        ? selectedLead
        : await ensurePersistedLead(selectedLead);
      const effectiveLead =
        resolvedLead.id === selectedLead.id
          ? selectedLead
          : ({
              ...resolvedLead,
              analysis_state: selectedLead.analysis_state,
              score_kind: selectedLead.score_kind,
              preview_summary: selectedLead.preview_summary,
              source: resolvedLead.source || selectedLead.source,
              source_label: resolvedLead.source_label || selectedLead.source_label,
            } as Lead);
      activeLeadId = effectiveLead.id;

      if (effectiveLead.id !== selectedLead.id) {
        const nextLeadRows = replaceLeadRow(workingLeadRows, selectedLead.id, effectiveLead);
        const nextProcessedDetails = replaceProcessedLeadDetails(
          workingProcessedDetails,
          selectedLead.id,
          effectiveLead.id
        );
        syncLeadListState({
          nextLeads: nextLeadRows,
          nextProcessedDetails,
          nextSelectedLeadId: effectiveLead.id,
        });
        setSelectedLead(effectiveLead);
        setSelectedLeadLive(effectiveLead);
        setSelectedLeadLiveDetails(nextProcessedDetails[effectiveLead.id] || null);
        workingLeadRows = nextLeadRows;
        workingProcessedDetails = nextProcessedDetails;
      }

      const controller = new AbortController();
      processControllersRef.current[effectiveLead.id] = controller;
      setProcessingIds((prev) => Array.from(new Set([...prev, effectiveLead.id])));

      const response = await fetch(ZRAI_ENDPOINTS.analyzeLead, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        signal: controller.signal,
        body: JSON.stringify({
          lead_id: effectiveLead.id,
          include_outreach: false,
          force_refresh: forceRefresh,
          lead: effectiveLead,
        }),
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }

      const payload = await response.json();
      const payloadData = getPayloadData(payload);
      const queued =
        payloadData?.queued ||
        payload?.queued ||
        payloadData?.analysis_state === "analyzing" ||
        payload?.analysis_state === "analyzing";

      if (queued) {
        const queuedLead = {
          ...effectiveLead,
          analysis_state: "analyzing",
        } as Lead;
        const mergedQueuedLeads = dedupeLeadRows(mergeLeadRows(workingLeadRows, [queuedLead]));
        const mergedQueuedDetails = {
          ...workingProcessedDetails,
          [queuedLead.id]: buildQueuedProcessedDetails(
            workingProcessedDetails?.[queuedLead.id] || null,
            payloadData?.analysis_updated_at || payload?.analysis_updated_at || null,
            forceRefresh
          ),
        };
        const resolvedQueuedLeadId = resolveSelectedLeadId(
          queuedLead.id,
          mergedQueuedLeads,
          [...workingLeadRows, queuedLead]
        );
        syncLeadListState({
          nextLeads: mergedQueuedLeads,
          nextProcessedDetails: mergedQueuedDetails,
          nextSelectedLeadId: resolvedQueuedLeadId,
        });
        setSelectedLead(
          mergedQueuedLeads.find((lead) => lead.id === resolvedQueuedLeadId) || queuedLead
        );
        setSelectedLeadLive(queuedLead);
        setSelectedLeadLiveDetails(mergedQueuedDetails[queuedLead.id] || null);
        toast.success(forceRefresh ? "Truth refresh started." : "Analysis started.");
        await pollLeadAnalysisCompletion(queuedLead.id);
        return;
      }

      if (!(payload?.success ?? true) || !payloadData?.lead) {
        throw new Error("Lead analysis failed.");
      }

      const analyzedLead = payloadData.lead as Lead;
      const analyzedProcessedDetailsRaw = {
        ...(payloadData.processed_details || {}),
        signal_facts: payloadData.signal_facts || payloadData.processed_details?.signal_facts || null,
        analysis_bundle: payloadData.analysis_bundle || payloadData.processed_details?.analysis_bundle || null,
        analysis_state: payloadData.analysis_state || payloadData.processed_details?.analysis_state || "analyzed",
        analysis_updated_at:
          payloadData.analysis_updated_at || payloadData.processed_details?.analysis_updated_at || null,
        signals_version: payloadData.signals_version || payloadData.processed_details?.signals_version || null,
      } as ProcessedLeadDetails;
      const hydrated = await hydrateFounderIntel(analyzedLead, analyzedProcessedDetailsRaw);

      const mergedLeads = dedupeLeadRows(mergeLeadRows(workingLeadRows, [hydrated.lead]));
      const mergedDetails = {
        ...workingProcessedDetails,
        [analyzedLead.id]: hydrated.processedDetails || analyzedProcessedDetailsRaw,
      };
      const resolvedAnalyzedLeadId = resolveSelectedLeadId(
        analyzedLead.id,
        mergedLeads,
        [...workingLeadRows, hydrated.lead]
      );
      syncLeadListState({
        nextLeads: mergedLeads,
        nextProcessedDetails: mergedDetails,
        nextSelectedLeadId: resolvedAnalyzedLeadId,
      });
      setSelectedLead(
        mergedLeads.find((lead) => lead.id === resolvedAnalyzedLeadId) || hydrated.lead
      );
      setSelectedLeadLive(hydrated.lead);
      setSelectedLeadLiveDetails(hydrated.processedDetails);
      toast.success(forceRefresh ? "Lead truth refreshed." : "Lead analyzed.");
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        toast.success("Lead analysis stopped.");
      } else {
        const failedDetails = {
          ...(processedDetailsRef.current?.[activeLeadId] || {}),
          analysis_state: "failed",
          analysis_updated_at: new Date().toISOString(),
          error: error instanceof Error ? error.message : "Lead analysis failed",
        } satisfies ProcessedLeadDetails;
        syncLeadListState({
          nextLeads: leadsRef.current,
          nextProcessedDetails: {
            ...(processedDetailsRef.current || {}),
            [activeLeadId]: failedDetails,
          },
          nextSelectedLeadId: activeLeadId,
        });
        setSelectedLeadLiveDetails(failedDetails);
        toast.error(error instanceof Error ? error.message : "Lead analysis failed");
      }
    } finally {
      const currentLeadIds = Array.from(
        new Set(
          [
            selectedLead.id,
            selectedLeadLive?.id,
            metadata?.liveSelectedLead?.id,
            ...selectedLeadEntityIds,
          ].filter(Boolean) as string[]
        )
      );
      clearProcessing(currentLeadIds);
      }
  };

  const resolvedSelectedLead = findLeadByEntity(leads, selectedLead) || selectedLead;
  const liveInspectorLead = selectedLeadLive || metadata?.liveSelectedLead || null;
  const liveInspectorDetails =
    selectedLeadLiveDetails ||
    metadata?.liveSelectedLeadDetails ||
    (liveInspectorLead?.id ? processedDetails?.[liveInspectorLead.id] || null : null);
  const selectedLeadDetailsFromStore = getProcessedDetailsForLead(
    processedDetails,
    leads,
    resolvedSelectedLead
  );
  const inspectorLead =
    hydrateLeadFromStoredAnalysis(liveInspectorLead, liveInspectorDetails) ||
    liveInspectorLead ||
    hydrateLeadFromStoredAnalysis(resolvedSelectedLead, selectedLeadDetailsFromStore) ||
    resolvedSelectedLead;
  const selectedLeadDetails =
    (inspectorLead?.id && liveInspectorLead?.id === inspectorLead.id
      ? liveInspectorDetails
      : null) || getProcessedDetailsForLead(processedDetails, leads, inspectorLead);
  const selectedLeadEffectiveState = getResolvedAnalysisState(inspectorLead, selectedLeadDetails);
  const selectedLeadEntityIds = inspectorLead
    ? Array.from(
        new Set(
          [
            ...leads
              .filter((lead) => isSameLeadEntity(lead, inspectorLead))
              .map((lead) => lead.id),
            inspectorLead.id,
            resolvedSelectedLead?.id,
            liveInspectorLead?.id,
          ].filter((leadId): leadId is string => Boolean(leadId))
        )
      )
    : [];
  const isSelectedLeadProcessing = selectedLead
    ? selectedLeadEntityIds.some((leadId) => processingIds.includes(leadId)) &&
      selectedLeadEffectiveState !== "analyzed" &&
      selectedLeadEffectiveState !== "failed"
    : false;
  const analysisBundle = getAnalysisBundle(inspectorLead, selectedLeadDetails);
  const signalFacts = getSignalFacts(inspectorLead, selectedLeadDetails);
  const contactIntel = getContactIntelligence(
    inspectorLead,
    selectedLeadDetails,
    signalFacts,
    analysisBundle
  );
  const scoreNarrative = buildLeadScoreNarrative(inspectorLead, selectedLeadDetails);
  const proofExtraction = selectedLeadDetails?.proof?.extraction_data as Record<string, unknown> | undefined;
  const proofFacts = getCanonicalProofFacts(signalFacts, proofExtraction);
  const proofInsights = getCanonicalProofInsights(
    signalFacts,
    proofExtraction,
    selectedLeadDetails?.proof?.audit_bullets
  );
  const outreachSummary = getVisibleOutreachDrafts(selectedLeadDetails?.outreach);
  const scoreSnapshot = getScoreSnapshot(inspectorLead, selectedLeadDetails);
  const hasFinalRows = leads.some((lead) => lead.score_kind === "final_score");
  const hasPreviewRows = leads.some((lead) => lead.score_kind !== "final_score");
  const avgScoreLabel = hasFinalRows && hasPreviewRows
    ? "Avg visible score"
    : hasFinalRows
      ? "Avg final"
      : "Avg match";

  if (leads.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center text-zinc-500">
          <div className="text-lg">No leads found</div>
          <div className="text-sm">Use the discover tool to find leads</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-row">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="border-zinc-200 border-b p-3 dark:border-zinc-700">
            <input
              className="w-full rounded-md border border-zinc-300 bg-transparent px-3 py-2 text-sm dark:border-zinc-600"
              onChange={(event) => {
                const nextFilter = event.target.value;
                setMetadata((prev: LeadListMetadata) => ({
                  ...prev,
                  filter: nextFilter,
                }));
                persistLeadListContent({
                  nextFilter,
                });
              }}
              placeholder="Filter leads..."
              type="text"
              value={filter}
            />
        </div>

        <div className="flex gap-4 border-zinc-200 border-b bg-zinc-50 p-3 text-sm dark:border-zinc-700 dark:bg-zinc-800">
          <span>Total: {leads.length}</span>
          <span>Filtered: {filteredLeads.length}</span>
          <span>
            {avgScoreLabel}:{" "}
            {Math.round(
              leads.reduce((sum, lead) => sum + (lead.score || 0), 0) /
                leads.length
            ) || 0}
          </span>
          <div className="ml-auto flex items-center gap-2">
            <label className="flex items-center gap-2 rounded-md border border-zinc-300 px-3 py-2 text-xs text-zinc-600 dark:border-zinc-700 dark:text-zinc-300">
              <input
                checked={autoAnalyzeEnabled}
                className="accent-emerald-500"
                onChange={(event) => {
                  const nextAutoAnalyzeEnabled = event.target.checked;
                  setMetadata((prev: LeadListMetadata) => ({
                    ...prev,
                    autoAnalyzeCompletedToken: nextAutoAnalyzeEnabled
                      ? null
                      : prev.autoAnalyzeCompletedToken,
                    autoAnalyzeEnabled: nextAutoAnalyzeEnabled,
                  }));
                  persistLeadListContent({
                    nextAutoAnalyzeCompletedToken: nextAutoAnalyzeEnabled
                      ? null
                      : autoAnalyzeCompletedToken,
                    nextAutoAnalyzeEnabled,
                  });
                  if (nextAutoAnalyzeEnabled) {
                    autoAnalyzeRunRef.current = null;
                  }
                }}
                type="checkbox"
              />
              Auto fast analyze
            </label>
            <button
              className="rounded-md bg-emerald-600 px-3 py-2 text-xs text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!dedupeLeadRows(displayLeads).length || !!processingIds.length}
              onClick={() =>
                void processLeads(
                  dedupeLeadRows(displayLeads).map((lead) => lead.id),
                  {
                    includeOutreach: false,
                    forceRefresh: true,
                    successMessage: `Analyzed ${dedupeLeadRows(displayLeads).length} visible lead${dedupeLeadRows(displayLeads).length === 1 ? "" : "s"}.`,
                    emptyMessage: "No visible leads were analyzed successfully.",
                  }
                )
              }
              type="button"
            >
              Analyze visible
            </button>
            {!!processingIds.length && (
              <button
                className="rounded-md border border-red-500/50 px-3 py-2 text-xs text-red-300 transition hover:bg-red-500/10"
                onClick={() => stopProcessing()}
                type="button"
              >
                Stop all
              </button>
            )}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-auto">
          <table className="w-full">
            <thead className="sticky top-0 bg-zinc-100 dark:bg-zinc-900">
              <tr>
                <th
                  className="cursor-pointer p-3 text-left font-medium text-sm"
                  onClick={() => handleSort("company_name")}
                >
                  Company{" "}
                  {sortBy === "company_name" &&
                    (sortOrder === "asc" ? "^" : "v")}
                </th>
                <th
                  className="cursor-pointer p-3 text-left font-medium text-sm"
                  onClick={() => handleSort("niche")}
                >
                  Verified fit{" "}
                  {sortBy === "niche" && (sortOrder === "asc" ? "^" : "v")}
                </th>
                <th className="p-3 text-left font-medium text-sm">Source</th>
                <th
                  className="cursor-pointer p-3 text-left font-medium text-sm"
                  onClick={() => handleSort("geo")}
                >
                  Geo {sortBy === "geo" && (sortOrder === "asc" ? "^" : "v")}
                </th>
                <th
                  className="cursor-pointer p-3 text-left font-medium text-sm"
                  onClick={() => handleSort("score")}
                >
                  Match / score{" "}
                  {sortBy === "score" && (sortOrder === "asc" ? "^" : "v")}
                </th>
                <th
                  className="cursor-pointer p-3 text-left font-medium text-sm"
                  onClick={() => handleSort("status")}
                >
                  Status{" "}
                  {sortBy === "status" && (sortOrder === "asc" ? "^" : "v")}
                </th>
                <th className="p-3 text-left font-medium text-sm">Contacts</th>
              </tr>
            </thead>
            <tbody>
              {displayLeads.map((lead, index) => (
                <LeadRow
                  key={getStableLeadKey(lead, index)}
                  lead={lead}
                  onClick={() => {
                    setSelectedLead(lead);
                    setSelectedLeadLive(null);
                    setSelectedLeadLiveDetails(null);
                    setMetadata((prev: LeadListMetadata) => ({
                      ...prev,
                      selectedLeadId: lead.id,
                      liveSelectedLead: null,
                      liveSelectedLeadDetails: null,
                    }));
                    persistLeadListContent({
                      nextSelectedLeadId: lead.id,
                    });
                  }}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {inspectorLead && (
        <aside className="w-[320px] shrink-0 border-zinc-200 border-l bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800">
          <div className="flex items-center justify-between border-zinc-200 border-b px-4 py-3 dark:border-zinc-700">
            <div className="font-medium text-sm text-zinc-500 uppercase tracking-[0.18em]">
              Lead inspector
            </div>
            <button
              className="text-blue-500 text-sm hover:underline"
              onClick={() => {
                setSelectedLead(null);
                setSelectedLeadLive(null);
                setSelectedLeadLiveDetails(null);
                setMetadata((prev: LeadListMetadata) => ({
                  ...prev,
                  selectedLeadId: null,
                  liveSelectedLead: null,
                  liveSelectedLeadDetails: null,
                }));
                persistLeadListContent({
                  nextSelectedLeadId: null,
                });
              }}
              type="button"
            >
              Close
            </button>
          </div>
          <div className="space-y-4 p-4">
            <div>
              <div className="font-bold text-lg">{getLeadDisplayName(inspectorLead)}</div>
              <div className="break-all text-sm text-zinc-500">
                {getLeadWebsiteHostValue(inspectorLead) || normalizeLeadDomainValue(inspectorLead.domain)}
              </div>
              {selectedLeadEffectiveState === "analyzed" && (
                <div className="mt-2 inline-flex rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                  Saved analysis
                </div>
              )}
              {selectedLeadEffectiveState === "failed" && (
                <div className="mt-2 inline-flex rounded-full bg-red-100 px-2.5 py-1 text-[11px] text-red-800 dark:bg-red-950 dark:text-red-300">
                  Analysis failed
                </div>
              )}
              {selectedLeadEffectiveState !== "analyzed" && (selectedLeadLive || metadata?.liveSelectedLead) && (
                <div className="mt-2 inline-flex rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                  Live backend state
                </div>
              )}
              {selectedLeadEffectiveState !== "analyzed" &&
                !selectedLeadLive &&
                !metadata?.liveSelectedLead &&
                inspectorLead.score_kind !== "final_score" && (
                <div className="mt-2 inline-flex rounded-full bg-amber-100 px-2.5 py-1 text-[11px] text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                  Snapshot preview
                </div>
              )}
              {selectedLeadEffectiveState !== "analyzed" &&
                (selectedLeadLive || metadata?.liveSelectedLead) &&
                selectedLead &&
                (() => {
                  const latestLead = selectedLeadLive || metadata?.liveSelectedLead;
                  return latestLead
                    ? selectedLead.score !== latestLead.score ||
                        selectedLead.score_kind !== latestLead.score_kind ||
                        selectedLead.analysis_state !== latestLead.analysis_state
                    : false;
                })() && (
                  <div className="mt-2 text-xs text-zinc-500">
                    Inspector is showing fresher backend truth. Use <span className="font-medium">Refresh truth</span> to sync the row.
                  </div>
                )}
              {getLeadSummary(inspectorLead) && (
                <div className="mt-2 text-sm text-zinc-500">
                  {getLeadSummary(inspectorLead)}
                </div>
              )}
              {selectedLeadDetails?.error && (
                <div className="mt-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
                  {selectedLeadDetails.error}
                </div>
              )}
              <div className="mt-2 text-sm text-zinc-500">
                {scoreNarrative.whyThisLead ||
                  scoreNarrative.nextBestAction ||
                  "Ranked contacts, score context, and proof stay visible below."}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Verified fit
                </div>
                <div className="mt-1">{getLeadFit(inspectorLead)}</div>
              </div>
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Source
                </div>
                <div className="mt-1">{getLeadSource(inspectorLead)}</div>
              </div>
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Geo
                </div>
                <div className="mt-1">{inspectorLead.geo}</div>
              </div>
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  {getScoreLabel(inspectorLead)}
                </div>
                <div className="mt-1">{inspectorLead.score ?? "-"}</div>
              </div>
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Analysis
                </div>
                <div className="mt-1">{getAnalysisLabel(inspectorLead)}</div>
              </div>
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Contacts
                </div>
                <div className="mt-1">{inspectorLead.contacts?.length || 0}</div>
              </div>
            </div>
            {signalFacts && (
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                      Decision
                    </div>
                    <div className="mt-1 text-lg font-semibold">
                      {getDecisionLabel(scoreSnapshot.finalScore)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                      Final score
                    </div>
                    <div className="mt-1 text-2xl font-bold">
                      {scoreSnapshot.finalScore ?? inspectorLead.score ?? "-"}
                    </div>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Demand</div>
                    <div className="mt-1">{scoreSnapshot.demand ?? "-"}</div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Trust</div>
                    <div className="mt-1">{scoreSnapshot.trust ?? "-"}</div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Leak</div>
                    <div className="mt-1">{scoreSnapshot.leak ?? "-"}</div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Offer fit</div>
                    <div className="mt-1">{scoreSnapshot.offerFit ?? "-"}</div>
                  </div>
                </div>
                <div className="mt-3 rounded-md bg-zinc-100 p-2 text-sm dark:bg-zinc-900">
                  <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Score context</div>
                  <div className="mt-2 space-y-1">
                    <div>
                      <span className="font-medium">Why pursue:</span>{" "}
                      {scoreNarrative.whyThisLead || "No intent narrative captured yet."}
                    </div>
                    <div>
                      <span className="font-medium">Trust:</span> {scoreNarrative.trustSummary}
                    </div>
                    <div>
                      <span className="font-medium">Leak:</span> {scoreNarrative.leakSummary}
                    </div>
                    <div>
                      <span className="font-medium">Offer fit:</span> {scoreNarrative.offerFitSummary}
                    </div>
                    {scoreNarrative.nextBestAction && (
                      <div>
                        <span className="font-medium">Next action:</span> {scoreNarrative.nextBestAction}
                      </div>
                    )}
                  </div>
                </div>
                <div className="mt-3 space-y-2 text-sm">
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <span className="font-medium">Top issue:</span> {getTopIssue(signalFacts)}
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <span className="font-medium">Next best action:</span> {getNextBestAction(signalFacts)}
                  </div>
                  {buildSocialResearchSummary(signalFacts) && (
                    <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                      <span className="font-medium">Growth signals:</span> {buildSocialResearchSummary(signalFacts)}
                    </div>
                  )}
                </div>
                {contactIntel.hasAny && (
                  <div className="mt-3 space-y-2 text-sm">
                    <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                      <span className="font-medium">Decision maker:</span>{" "}
                      {contactIntel.decisionMakerName || "Likely doctor/owner contact not confirmed yet"}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Role</div>
                        <div className="mt-1">{contactIntel.decisionMakerRole || "primary contact"}</div>
                      </div>
                      <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Best channel</div>
                        <div className="mt-1">{formatBestContactChannel(contactIntel.bestContactChannel)}</div>
                      </div>
                      <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Best phone</div>
                        <div className="mt-1 break-all">{contactIntel.bestContactPhone || "-"}</div>
                      </div>
                      <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Best email</div>
                        <div className="mt-1 break-all">{contactIntel.bestContactEmail || "-"}</div>
                      </div>
                    </div>
                    {(contactIntel.decisionMakerSource || contactIntel.decisionMakerConfidence != null) && (
                      <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Contact confidence</div>
                        <div className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
                          {[
                            contactIntel.decisionMakerSource ? `Source: ${contactIntel.decisionMakerSource}` : null,
                            contactIntel.decisionMakerConfidence != null
                              ? `Confidence: ${
                                  contactIntel.decisionMakerConfidence <= 1
                                    ? `${Math.round(contactIntel.decisionMakerConfidence * 100)}%`
                                    : `${Math.round(contactIntel.decisionMakerConfidence)}/100`
                                }`
                              : null,
                          ]
                            .filter(Boolean)
                            .join(" | ")}
                        </div>
                      </div>
                    )}
                    {contactIntel.decisionMakerLinkedin && (
                      <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">LinkedIn</div>
                        <a
                          className="mt-1 block break-all text-blue-500 hover:underline"
                          href={contactIntel.decisionMakerLinkedin}
                          rel="noreferrer"
                          target="_blank"
                        >
                          {contactIntel.decisionMakerLinkedin}
                        </a>
                      </div>
                    )}
                    {!!contactIntel.decisionMakerCandidates.length && (
                      <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Likely contacts</div>
                        <div className="mt-2 space-y-1 text-xs">
                          {contactIntel.decisionMakerCandidates.slice(0, 6).map((candidate, index) => (
                            <div key={`candidate-${index}`} className="rounded border border-zinc-200 px-2 py-1 dark:border-zinc-800">
                              <div className="font-medium">{String(candidate.name || "Unknown contact")}</div>
                              <div className="text-zinc-500 dark:text-zinc-400">
                                {[candidate.role, candidate.clinic, candidate.source].filter(Boolean).join(" | ") || "decision-maker candidate"}
                              </div>
                              {!!candidate.phones?.length && (
                                <div className="mt-1 text-zinc-600 dark:text-zinc-300">
                                  {candidate.phones.slice(0, 2).join(" | ")}
                                </div>
                              )}
                              {!!candidate.emails?.length && (
                                <div className="mt-1 break-all text-zinc-600 dark:text-zinc-300">
                                  {candidate.emails.slice(0, 2).join(" | ")}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {!!contactIntel.branchContacts.length && (
                      <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Branch phones</div>
                        <div className="mt-2 space-y-1 text-xs">
                          {contactIntel.branchContacts.slice(0, 6).map((contact, index) => (
                            <div key={`branch-contact-${index}`} className="rounded border border-zinc-200 px-2 py-1 dark:border-zinc-800">
                              <div className="font-medium">{String(contact.name || "Clinic branch")}</div>
                              <div className="text-zinc-500 dark:text-zinc-400">{String(contact.phone || "-")}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {(contactIntel.bestContactReason || contactIntel.recommendedOffer || contactIntel.decisionMakerSource) && (
                      <div className="rounded-md bg-zinc-100 p-2 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
                        {contactIntel.bestContactReason || contactIntel.recommendedOffer || contactIntel.decisionMakerSource}
                      </div>
                    )}
                    {!!contactIntel.contactEvidence.length && (
                      <div className="rounded-md bg-zinc-100 p-2 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
                        {contactIntel.contactEvidence.join(" | ")}
                      </div>
                    )}
                  </div>
                )}
                <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Phone</div>
                    <div className="mt-1">{signalFacts.phone_visible ? "Yes" : "No"}</div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Booking</div>
                    <div className="mt-1">{signalFacts.booking_detected ? "Yes" : "No"}</div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">WhatsApp</div>
                    <div className="mt-1">{signalFacts.whatsapp_detected ? "Yes" : "No"}</div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Reviews</div>
                    <div className="mt-1">{signalFacts.reviews_count ?? "-"}</div>
                    <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                      {getFactSourceLabel(signalFacts, "reviews")}
                    </div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Rating</div>
                    <div className="mt-1">{signalFacts.rating ?? "-"}</div>
                    <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                      {getFactSourceLabel(signalFacts, "rating")}
                    </div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Doctors</div>
                    <div className="mt-1">{signalFacts.doctor_count || "-"}</div>
                    {!!contactIntel.doctorNames.length && (
                      <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                        {contactIntel.doctorNames.slice(0, 4).join(", ")}
                      </div>
                    )}
                    <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                      {getFactSourceLabel(signalFacts, "doctors")}
                    </div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Locations</div>
                    <div className="mt-1">{formatLocationFact(signalFacts)}</div>
                    <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                      {getFactSourceLabel(signalFacts, "locations")}
                    </div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Ads</div>
                    <div className="mt-1">{formatAdsFact(signalFacts)}</div>
                    {!!signalFacts.ads_channels?.length && (
                      <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                        {signalFacts.ads_channels.join(", ")}
                      </div>
                    )}
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Instagram</div>
                    <div className="mt-1">
                      {signalFacts.instagram_profile?.followers_count != null
                        ? formatSocialCount(signalFacts.instagram_profile.followers_count, "followers")
                        : signalFacts.instagram_present
                          ? "Present"
                          : "No"}
                    </div>
                    <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                      {getFactSourceLabel(signalFacts, "instagram")}
                    </div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">YouTube</div>
                    <div className="mt-1">
                      {signalFacts.youtube_channel?.subscriber_count != null
                        ? formatSocialCount(signalFacts.youtube_channel.subscriber_count, "subs")
                        : signalFacts.youtube_present
                          ? "Present"
                          : "No"}
                    </div>
                    <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                      {getFactSourceLabel(signalFacts, "youtube")}
                    </div>
                  </div>
                </div>
                {(signalFacts.instagram_profile || signalFacts.youtube_channel) && (
                  <div className="mt-3 space-y-3">
                    {signalFacts.instagram_profile && (
                      <div className="rounded-md bg-zinc-100 p-3 dark:bg-zinc-900">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Instagram demand</div>
                            <div className="mt-1 text-sm font-medium">
                              {signalFacts.instagram_profile.full_name ||
                                (signalFacts.instagram_profile.username
                                  ? `@${signalFacts.instagram_profile.username}`
                                  : "Instagram profile")}
                            </div>
                            <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                              {getFactSourceLabel(signalFacts, "instagram")}
                            </div>
                          </div>
                          {signalFacts.instagram_profile.profile_url && (
                            <a
                              className="text-xs text-blue-500 hover:underline"
                              href={signalFacts.instagram_profile.profile_url}
                              rel="noreferrer"
                              target="_blank"
                            >
                              Open profile
                            </a>
                          )}
                        </div>
                        <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                          <div className="rounded-md border border-zinc-200 p-2 dark:border-zinc-700">
                            <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Followers</div>
                            <div className="mt-1">{formatSocialMetric(signalFacts.instagram_profile.followers_count)}</div>
                          </div>
                          <div className="rounded-md border border-zinc-200 p-2 dark:border-zinc-700">
                            <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Posts</div>
                            <div className="mt-1">{formatSocialMetric(signalFacts.instagram_profile.posts_count)}</div>
                          </div>
                          <div className="rounded-md border border-zinc-200 p-2 dark:border-zinc-700">
                            <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Following</div>
                            <div className="mt-1">{formatSocialMetric(signalFacts.instagram_profile.following_count)}</div>
                          </div>
                          <div className="rounded-md border border-zinc-200 p-2 dark:border-zinc-700">
                            <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Recent posts</div>
                            <div className="mt-1">{formatSocialMetric(signalFacts.instagram_profile.latest_post_count)}</div>
                          </div>
                        </div>
                        <div className="mt-2 text-sm text-zinc-500">
                          {buildInstagramBehaviorSummary(signalFacts)}
                        </div>
                        {(signalFacts.instagram_profile.business_category ||
                          signalFacts.instagram_profile.email ||
                          signalFacts.instagram_profile.external_url) && (
                          <div className="mt-2 space-y-1 text-sm text-zinc-500">
                            {signalFacts.instagram_profile.business_category && (
                              <div>Category: {signalFacts.instagram_profile.business_category}</div>
                            )}
                            {signalFacts.instagram_profile.email && (
                              <div className="break-all">Email: {signalFacts.instagram_profile.email}</div>
                            )}
                            {signalFacts.instagram_profile.external_url && (
                              <a
                                className="break-all text-blue-500 hover:underline"
                                href={signalFacts.instagram_profile.external_url}
                                rel="noreferrer"
                                target="_blank"
                              >
                                {signalFacts.instagram_profile.external_url}
                              </a>
                            )}
                          </div>
                        )}
                        {signalFacts.instagram_profile.bio && (
                          <div className="mt-2 rounded-md border border-zinc-200 p-2 text-sm text-zinc-500 dark:border-zinc-700">
                            {signalFacts.instagram_profile.bio}
                          </div>
                        )}
                      </div>
                    )}
                    {signalFacts.youtube_channel && (
                      <div className="rounded-md bg-zinc-100 p-3 dark:bg-zinc-900">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">YouTube demand</div>
                            <div className="mt-1 text-sm font-medium">
                              {signalFacts.youtube_channel.channel_name || "YouTube channel"}
                            </div>
                            <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                              {getFactSourceLabel(signalFacts, "youtube")}
                            </div>
                          </div>
                          {signalFacts.youtube_channel.channel_url && (
                            <a
                              className="text-xs text-blue-500 hover:underline"
                              href={signalFacts.youtube_channel.channel_url}
                              rel="noreferrer"
                              target="_blank"
                            >
                              Open channel
                            </a>
                          )}
                        </div>
                        <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                          <div className="rounded-md border border-zinc-200 p-2 dark:border-zinc-700">
                            <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Subscribers</div>
                            <div className="mt-1">{formatSocialMetric(signalFacts.youtube_channel.subscriber_count)}</div>
                          </div>
                          <div className="rounded-md border border-zinc-200 p-2 dark:border-zinc-700">
                            <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Total views</div>
                            <div className="mt-1">{formatSocialMetric(signalFacts.youtube_channel.total_views)}</div>
                          </div>
                          <div className="rounded-md border border-zinc-200 p-2 dark:border-zinc-700">
                            <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Videos</div>
                            <div className="mt-1">{formatSocialMetric(signalFacts.youtube_channel.total_videos)}</div>
                          </div>
                          <div className="rounded-md border border-zinc-200 p-2 dark:border-zinc-700">
                            <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Avg recent views</div>
                            <div className="mt-1">{formatSocialMetric(signalFacts.youtube_channel.avg_recent_views)}</div>
                          </div>
                        </div>
                        <div className="mt-2 text-sm text-zinc-500">
                          {buildYouTubeBehaviorSummary(signalFacts)}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
            <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
              <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                Status
              </div>
              <div className="mt-2 inline-flex rounded-full bg-zinc-200 px-2.5 py-1 text-xs dark:bg-zinc-700">
                {formatLeadStatus(inspectorLead.status)}
              </div>
              <div className="mt-2 text-sm text-zinc-500">
                {getStatusHelp(inspectorLead.status)}
              </div>
            </div>
            {!!inspectorLead.contacts?.length && (
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Actual contacts
                </div>
                <div className="mt-2 space-y-2 text-sm">
                  {inspectorLead.contacts.map((contact, index) => (
                    <div
                      key={getStableContactKey(inspectorLead.id, contact, index)}
                      className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900"
                    >
                      <div className="font-medium">{contact.name}</div>
                      {contact.title && <div className="text-zinc-500">{contact.title}</div>}
                      {contact.phone && <div>{contact.phone}</div>}
                      {contact.email && <div>{contact.email}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {!!inspectorLead.contact_paths?.length && (
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Contact paths
                </div>
                <div className="mt-2 text-sm">
                  {inspectorLead.contact_paths.map(formatContactPath).join(", ")}
                </div>
                <div className="mt-2 text-sm text-zinc-500">
                  These are only the paths actually detected on this site, not a generic list.
                </div>
              </div>
            )}
            {selectedLeadDetails?.intent && (
              <details className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <summary className="cursor-pointer text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Intent summary
                </summary>
                {Boolean(selectedLeadDetails.intent.site_truth_summary) && (
                  <div className="mb-2 mt-3 rounded-md bg-zinc-100 p-2 text-sm dark:bg-zinc-900">
                    {String(selectedLeadDetails.intent.site_truth_summary)}
                  </div>
                )}
                <div className="mt-2 text-sm">
                  {(selectedLeadDetails.intent.why_this_lead as string) || "No intent summary captured."}
                </div>
              </details>
            )}
            {selectedLeadDetails?.proof && (
              <details className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <summary className="cursor-pointer text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Proof details
                </summary>
                <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Booking target</div>
                    <div className="mt-1 break-all">{proofFacts.bookingTarget || "not detected"}</div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">WhatsApp target</div>
                    <div className="mt-1 break-all">{proofFacts.whatsappTarget || "not extracted"}</div>
                  </div>
                </div>
                {!!proofInsights.length && (
                  <div className="mt-3 space-y-2 text-sm">
                    {proofInsights.map((insight, index) => (
                      <div key={`${selectedLead?.id ?? "selected"}-proof-${index}`} className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        {insight}
                      </div>
                    ))}
                  </div>
                )}
                <div className="mt-3 grid grid-cols-2 gap-2">
                  {selectedLeadDetails.proof.hero_screenshot_url && (
                    <a
                      className="overflow-hidden rounded-md border border-zinc-200 dark:border-zinc-700"
                      href={selectedLeadDetails.proof.hero_screenshot_url}
                      rel="noreferrer"
                      target="_blank"
                    >
                      <img
                        alt="Hero proof"
                        className="h-24 w-full object-cover"
                        src={selectedLeadDetails.proof.hero_screenshot_url}
                      />
                    </a>
                  )}
                  {selectedLeadDetails.proof.cta_screenshot_url && (
                    <a
                      className="overflow-hidden rounded-md border border-zinc-200 dark:border-zinc-700"
                      href={selectedLeadDetails.proof.cta_screenshot_url}
                      rel="noreferrer"
                      target="_blank"
                    >
                      <img
                        alt="CTA proof"
                        className="h-24 w-full object-cover"
                        src={selectedLeadDetails.proof.cta_screenshot_url}
                      />
                    </a>
                  )}
                </div>
              </details>
            )}
            {!!outreachSummary.drafts.length && (
              <details className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <summary className="cursor-pointer text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Outreach drafts
                </summary>
                <div className="mt-2 text-xs text-zinc-500">
                  Showing the latest unique drafts only.
                </div>
                <div className="mt-3 space-y-2 text-sm">
                  {outreachSummary.drafts.map((message, index) => (
                    <div key={`${selectedLead?.id ?? "selected"}-outreach-${index}`} className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                      <div className="font-medium">
                        {message.subject || `${message.channel || "message"} draft`}
                      </div>
                      {message.body && (
                        <div className="mt-1 line-clamp-4 text-zinc-600 dark:text-zinc-300">
                          {message.body}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                {!!outreachSummary.hiddenCount && (
                  <div className="mt-2 text-xs text-zinc-500">
                    {outreachSummary.hiddenCount} older duplicate draft
                    {outreachSummary.hiddenCount === 1 ? "" : "s"} hidden.
                  </div>
                )}
              </details>
            )}
            <div className="flex flex-wrap gap-2">
              {isSelectedLeadProcessing ? (
                <button
                  className="rounded-md bg-red-600 px-3 py-2 text-sm text-white transition hover:bg-red-500"
                  onClick={() => {
                    if (!selectedLead?.id) {
                      return;
                    }
                    stopProcessing(selectedLeadEntityIds);
                  }}
                  type="button"
                >
                  Stop analyze
                </button>
              ) : (
                <button
                  className="rounded-md bg-emerald-600 px-3 py-2 text-sm text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={isSelectedLeadProcessing}
                  onClick={() => void analyzeSelectedLead(true)}
                  type="button"
                >
                  Analyze lead
                </button>
              )}
              <button
                className="rounded-md border border-zinc-300 px-3 py-2 text-sm transition hover:bg-zinc-100 dark:border-zinc-600 dark:hover:bg-zinc-900"
                disabled={!inspectorLead}
                onClick={() => {
                  navigator.clipboard.writeText(
                    formatLeadForClipboard(inspectorLead, selectedLeadDetails || null)
                  );
                  toast.success("Live lead summary copied.");
                }}
                type="button"
              >
                Copy summary
              </button>
              <button
                className="rounded-md border border-zinc-300 px-3 py-2 text-sm transition hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-600 dark:hover:bg-zinc-900"
                disabled={isRefreshingTruth || isSelectedLeadProcessing}
                onClick={() => void refreshSelectedLeadTruth()}
                type="button"
              >
                {isRefreshingTruth ? "Refreshing..." : "Refresh truth"}
              </button>
              {!!processingIds.length && !isSelectedLeadProcessing && (
                <button
                  className="rounded-md border border-red-500/50 px-3 py-2 text-sm text-red-300 transition hover:bg-red-500/10"
                  onClick={() => stopProcessing()}
                  type="button"
                >
                  Stop all
                </button>
              )}
            </div>
            {isSelectedLeadProcessing && (
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200">
                Running fast lead analysis for this lead: enrichment, intent fit, scoring, and backend truth sync. Click{" "}
                Stop analyze to cancel it.
              </div>
            )}
          </div>
        </aside>
      )}
    </div>
  );
}

export const leadListArtifact = new Artifact<"lead-list", LeadListMetadata>({
  kind: "lead-list",
  description:
    "Display a list of leads with filtering and sorting capabilities",
  initialize: ({ setMetadata }) => {
    setMetadata((prev: Partial<LeadListMetadata> | null) => ({
      leads: prev?.leads ?? [],
      loading: prev?.loading ?? false,
      sortBy: prev?.sortBy ?? "score",
      sortOrder: prev?.sortOrder ?? "desc",
      filter: prev?.filter ?? "",
      autoAnalyzeCompletedToken: prev?.autoAnalyzeCompletedToken ?? null,
      autoAnalyzeEnabled: prev?.autoAnalyzeEnabled ?? true,
      selectedLeadId: prev?.selectedLeadId ?? null,
      processedDetails: prev?.processedDetails ?? {},
    }));
  },
  onStreamPart: ({ streamPart, setArtifact, setMetadata }) => {
    if ((streamPart as any).type === "data-leadList") {
      const data = (streamPart as any).data as Lead[] | LeadListPayload;
      const payload = Array.isArray(data) ? ({ leads: data } satisfies LeadListPayload) : data;
      const incomingLeads = dedupeLeadRows(sanitizeLeadRows(payload.leads || []));
      const incomingProcessedDetails = payload.processedDetails || payload.processed_details || {};
      setMetadata((prev: LeadListMetadata) => {
        const nextProcessedDetails = mergeProcessedDetailsMapRecords(
          prev.processedDetails || {},
          incomingProcessedDetails
        );
        return {
          ...prev,
          filter: payload.filter || prev.filter || "",
          autoAnalyzeCompletedToken:
            payload.autoAnalyzeCompletedToken || prev.autoAnalyzeCompletedToken || null,
          autoAnalyzeEnabled: payload.autoAnalyzeEnabled ?? prev.autoAnalyzeEnabled ?? true,
          leads: dedupeLeadRows(
            mergeLeadRows(
              dedupeLeadRows(sanitizeLeadRows(prev?.leads || [])),
              incomingLeads
            ).map(
              (lead) =>
                hydrateLeadFromStoredAnalysis(
                  lead,
                  nextProcessedDetails[lead.id] || null
                ) || lead
            )
          ),
          loading: false,
          processedDetails: nextProcessedDetails,
          selectedLeadId:
            resolveSelectedLeadId(
              payload.selectedLeadId || prev.selectedLeadId || null,
              dedupeLeadRows(
                mergeLeadRows(
                  dedupeLeadRows(sanitizeLeadRows(prev?.leads || [])),
                  incomingLeads
                )
              ),
              [...dedupeLeadRows(sanitizeLeadRows(prev?.leads || [])), ...incomingLeads]
            ) || null,
          sortBy: payload.sortBy || prev.sortBy || "score",
          sortOrder: payload.sortOrder || prev.sortOrder || "desc",
        };
      });
      setArtifact((draft) => ({
        ...draft,
        content: (() => {
          const currentPayload = parseLeadListPayload(draft.content || "");
          const mergedDetails = mergeProcessedDetailsMapRecords(
            currentPayload.processedDetails || {},
            incomingProcessedDetails
          );
          const canonicalMergedLeads = mergeLeadRows(currentPayload.leads, incomingLeads);
          const mergedLeads = dedupeLeadRows(
            canonicalMergedLeads.map(
              (lead) =>
                hydrateLeadFromStoredAnalysis(
                  lead,
                  getProcessedDetailsForLead(mergedDetails, canonicalMergedLeads, lead)
                ) || lead
            )
          );
          return serializeLeadListPayload(mergedLeads, {
            autoAnalyzeCompletedToken:
              payload.autoAnalyzeCompletedToken ||
              currentPayload.autoAnalyzeCompletedToken ||
              null,
            autoAnalyzeEnabled:
              payload.autoAnalyzeEnabled ?? currentPayload.autoAnalyzeEnabled ?? true,
            filter: payload.filter || currentPayload.filter || "",
            processedDetails: mergedDetails,
            selectedLeadId:
              resolveSelectedLeadId(
                payload.selectedLeadId || currentPayload.selectedLeadId || null,
                mergedLeads,
                [...currentPayload.leads, ...incomingLeads]
              ) || null,
            sortBy: payload.sortBy || currentPayload.sortBy || "score",
            sortOrder: payload.sortOrder || currentPayload.sortOrder || "desc",
          });
        })(),
        status: "idle",
      }));
    }
  },
  content: (props) => (
    <LeadListContent
      content={props.content}
      metadata={props.metadata}
      setMetadata={props.setMetadata}
    />
  ),
  actions: [
    {
      icon: <UndoIcon size={18} />,
      description: "View Previous version",
      onClick: ({ handleVersionChange }) => handleVersionChange("prev"),
      isDisabled: ({ currentVersionIndex }) => currentVersionIndex === 0,
    },
    {
      icon: <RedoIcon size={18} />,
      description: "View Next version",
      onClick: ({ handleVersionChange }) => handleVersionChange("next"),
      isDisabled: ({ isCurrentVersion }) => isCurrentVersion,
    },
    {
      icon: <CopyIcon size={18} />,
      description: "Copy lead summary",
      onClick: ({ content, metadata }) => {
        try {
          if (metadata?.liveSelectedLead) {
            navigator.clipboard.writeText(
              formatLeadForClipboard(
                metadata.liveSelectedLead,
                metadata.liveSelectedLeadDetails || null
              )
            );
            toast.success("Live lead summary copied!");
            return;
          }
          const parsed = JSON.parse(content);
          const leads = Array.isArray(parsed) ? parsed : parsed.leads || [];
          const readable = formatLeadListForClipboard(
            leads,
            metadata?.processedDetails ||
              parsed.processedDetails ||
              parsed.processed_details ||
              {},
            metadata?.selectedLeadId || null
          );
          navigator.clipboard.writeText(readable);
          toast.success(
            metadata?.selectedLeadId ? "Lead inspector copied!" : "Lead list copied!"
          );
        } catch {
          navigator.clipboard.writeText(content);
          toast.success("Copied!");
        }
      },
    },
    {
      icon: <span className="font-semibold text-[10px]">AI</span>,
      label: "Analyze visible",
      description: "Run analysis truth, scoring, and proof for all visible leads",
      onClick: async ({ content, metadata, setArtifact, setMetadata }) => {
        try {
          const contentPayload = parseLeadListPayload(content);
          const contentLeads = contentPayload.leads;
          const metadataLeads = dedupeLeadRows(sanitizeLeadRows(metadata?.leads || []));
          const mergedProcessedDetails = mergeProcessedDetailsMapRecords(
            contentPayload.processedDetails || {},
            metadata?.processedDetails || {}
          );
          const mergedCanonicalLeadRows = mergeLeadRows(contentLeads, metadataLeads);
          const canonicalLeads = dedupeLeadRows(
            mergedCanonicalLeadRows.map(
              (lead) =>
                hydrateLeadFromStoredAnalysis(
                  lead,
                  getProcessedDetailsForLead(
                    mergedProcessedDetails,
                    mergedCanonicalLeadRows,
                    lead
                  )
                ) || lead
            )
          );
          const filteredLeads = filterLeads(
            canonicalLeads,
            metadata?.filter || contentPayload.filter || ""
          );
          const sortedLeads = sortLeads(
            filteredLeads,
            metadata?.sortBy || contentPayload.sortBy || "score",
            metadata?.sortOrder || contentPayload.sortOrder || "desc"
          );
          const visibleLeads = dedupeLeadRows(sortedLeads);
          if (visibleLeads.length === 0) {
            toast.error("No leads available to process.");
            return;
          }
          const persistedTopLeads = await Promise.all(
            visibleLeads.map((lead) =>
              isUuidLeadId(lead.id) ? Promise.resolve(lead) : ensurePersistedLead(lead)
            )
          );
          const replacedLeadRows = visibleLeads.reduce((nextLeads, lead, index) => {
            const importedLead = persistedTopLeads[index];
            return importedLead.id === lead.id
              ? nextLeads
              : replaceLeadRow(nextLeads, lead.id, importedLead);
          }, canonicalLeads);
          const replacedProcessedDetails = visibleLeads.reduce(
            (nextDetails, lead, index) =>
              persistedTopLeads[index].id === lead.id
                ? nextDetails
                : replaceProcessedLeadDetails(nextDetails, lead.id, persistedTopLeads[index].id),
            mergedProcessedDetails
          );
          if (replacedLeadRows !== canonicalLeads || replacedProcessedDetails !== mergedProcessedDetails) {
            setMetadata((prev: LeadListMetadata) => ({
              ...prev,
              leads: replacedLeadRows,
              processedDetails: replacedProcessedDetails,
            }));
          }
          const response = await fetch(ZRAI_ENDPOINTS.processLeads, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              lead_ids: Array.from(new Set(persistedTopLeads.map((lead) => lead.id))),
              include_outreach: false,
              force_refresh: true,
            }),
          });
          if (!response.ok) {
            throw new Error(await response.text());
          }
          const payload = getPayloadData((await response.json()) as {
            processed?: ProcessedLeadResponseItem[];
          });
          const processedItems = payload.processed || [];
          const processedLeads = processedItems
            .filter((item: ProcessedLeadResponseItem) => item.success && item.lead)
            .map((item: ProcessedLeadResponseItem) => item.lead as Lead);
          const processedDetailEntries = processedItems
            .filter((item: ProcessedLeadResponseItem) => item.success && item.lead)
            .map((item: ProcessedLeadResponseItem) => [
              item.lead!.id,
              {
                enrichment: item.enrichment || {},
                intent: item.intent || {},
                proof: item.proof || {},
                outreach: item.outreach || [],
                scoring: item.scoring || {},
                signal_facts: item.signal_facts,
                analysis_bundle: item.analysis_bundle,
                analysis_state: item.analysis_state,
                analysis_updated_at: item.analysis_updated_at,
                signals_version: item.signals_version,
                error: undefined,
              } satisfies ProcessedLeadDetails,
            ] as const);
          const failedDetailEntries = processedItems
            .filter((item: ProcessedLeadResponseItem) => !item.success)
            .map((item: ProcessedLeadResponseItem) => [
              item.lead_id,
              {
                ...(replacedProcessedDetails?.[item.lead_id] || {}),
                analysis_state: "failed",
                analysis_updated_at: new Date().toISOString(),
                error: item.error || "Lead analysis failed",
              } satisfies ProcessedLeadDetails,
            ] as const);
          if (processedLeads.length === 0) {
            setMetadata((prev: LeadListMetadata) => ({
              ...prev,
              processedDetails: {
                ...(prev.processedDetails || {}),
                ...Object.fromEntries(failedDetailEntries),
              },
            }));
            toast.error("No leads were processed successfully.");
            return;
          }
          const baseMetadata = (metadata || {}) as LeadListMetadata;
          const nextLeads = mergeLeadRows(replacedLeadRows, processedLeads);
          const nextProcessedDetails = mergeProcessedDetailsMapRecords(
            mergeProcessedDetailsMapRecords(
              replacedProcessedDetails || {},
              Object.fromEntries(processedDetailEntries)
            ),
            Object.fromEntries(failedDetailEntries)
          );
          const nextSelectedLeadId = resolveSelectedLeadId(
            baseMetadata.selectedLeadId || null,
            nextLeads,
            [...replacedLeadRows, ...processedLeads]
          );
          const nextContent = serializeLeadListPayload(nextLeads, {
            autoAnalyzeCompletedToken: baseMetadata.autoAnalyzeCompletedToken || null,
            autoAnalyzeEnabled: baseMetadata.autoAnalyzeEnabled ?? true,
            filter: baseMetadata.filter || "",
            processedDetails: nextProcessedDetails,
            selectedLeadId: nextSelectedLeadId,
            sortBy: baseMetadata.sortBy || "score",
            sortOrder: baseMetadata.sortOrder || "desc",
          });

          setMetadata((prev: LeadListMetadata) => ({
            ...prev,
            leads: nextLeads,
            processedDetails: nextProcessedDetails,
            selectedLeadId: nextSelectedLeadId,
          }));
          setArtifact((draft) => ({
            ...draft,
            content: nextContent,
          }));

          toast.success(
            `Analyzed ${processedLeads.length} visible lead${processedLeads.length === 1 ? "" : "s"}.`
          );
        } catch (error) {
          toast.error(error instanceof Error ? error.message : "Processing failed");
        }
      },
    },
  ],
  toolbar: [
    {
      icon: <span className="font-semibold text-[10px]">EN</span>,
      description: "Enrich all leads",
      onClick: async ({ content, metadata, setArtifact, setMetadata }) => {
        try {
          const parsed = JSON.parse(content || "{}");
          const contentLeads = (Array.isArray(parsed) ? parsed : parsed.leads || []) as Lead[];
          const visibleLeads = sortLeads(
            filterLeads(metadata?.leads?.length ? metadata.leads : contentLeads, metadata?.filter || ""),
            metadata?.sortBy || "score",
            metadata?.sortOrder || "desc"
          );

          if (!visibleLeads.length) {
            toast.error("No visible leads to enrich.");
            return;
          }

          const enrichedLeads: Lead[] = [];
          for (const rawLead of visibleLeads) {
            const lead = isUuidLeadId(rawLead.id) ? rawLead : await ensurePersistedLead(rawLead);
            const response = await fetch(ZRAI_ENDPOINTS.enrich, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ lead_id: lead.id }),
            });

            if (!response.ok) {
              continue;
            }

            const payload = await response.json();
            const payloadData = getPayloadData(payload);
            if ((payload?.success ?? true) && payloadData?.lead) {
              enrichedLeads.push(payloadData.lead as Lead);
            }
          }

          if (!enrichedLeads.length) {
            toast.error("No leads were enriched successfully.");
            return;
          }

          setMetadata((prev: LeadListMetadata) => {
            const nextLeads = mergeLeadRows(prev.leads, enrichedLeads);
            const nextContent = serializeLeadListPayload(nextLeads, {
              filter: prev.filter,
              processedDetails: prev.processedDetails,
              sortBy: prev.sortBy,
              sortOrder: prev.sortOrder,
            });
            setArtifact((draft) => ({
              ...draft,
              content: nextContent,
            }));
            return {
              ...prev,
              leads: nextLeads,
            };
          });

          toast.success(`Enriched ${enrichedLeads.length} lead${enrichedLeads.length === 1 ? "" : "s"}.`);
        } catch (error) {
          toast.error(error instanceof Error ? error.message : "Enrichment failed");
        }
      },
    },
    {
      icon: <span className="font-semibold text-[10px]">SC</span>,
      description: "Score all leads",
      onClick: async ({ content, metadata, setArtifact, setMetadata }) => {
        try {
          const parsed = JSON.parse(content || "{}");
          const contentLeads = (Array.isArray(parsed) ? parsed : parsed.leads || []) as Lead[];
          const visibleLeads = sortLeads(
            filterLeads(metadata?.leads?.length ? metadata.leads : contentLeads, metadata?.filter || ""),
            metadata?.sortBy || "score",
            metadata?.sortOrder || "desc"
          );

          if (!visibleLeads.length) {
            toast.error("No visible leads to score.");
            return;
          }

          const response = await fetch(ZRAI_ENDPOINTS.score, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              lead_ids: await Promise.all(
                visibleLeads.map(async (lead) =>
                  isUuidLeadId(lead.id) ? lead.id : (await ensurePersistedLead(lead)).id
                )
              ),
            }),
          });

          if (!response.ok) {
            throw new Error(await response.text());
          }

          const payload = await response.json();
          const scoredResults = getScoreResults(payload);
          const scoredLeads = scoredResults
            .map((result: { lead?: Lead; score_breakdown?: { total_score?: number }; breakdown?: { total_score?: number } }) =>
              result.lead
                ? {
                    ...result.lead,
                    score:
                      result.score_breakdown?.total_score ??
                      result.breakdown?.total_score ??
                      result.lead.score,
                    score_kind: "final_score" as const,
                    analysis_state: "analyzed" as const,
                  }
                : null
            )
            .filter(Boolean) as Lead[];

          if (!scoredLeads.length) {
            toast.error("Scoring did not return any leads.");
            return;
          }

          setMetadata((prev: LeadListMetadata) => {
            const nextLeads = mergeLeadRows(prev.leads, scoredLeads);
            const nextContent = serializeLeadListPayload(nextLeads, {
              filter: prev.filter,
              processedDetails: prev.processedDetails,
              sortBy: prev.sortBy,
              sortOrder: prev.sortOrder,
            });
            setArtifact((draft) => ({
              ...draft,
              content: nextContent,
            }));
            return {
              ...prev,
              leads: nextLeads,
            };
          });

          toast.success(`Scored ${scoredLeads.length} lead${scoredLeads.length === 1 ? "" : "s"}.`);
        } catch (error) {
          toast.error(error instanceof Error ? error.message : "Scoring failed");
        }
      },
    },
  ],
});


