import { randomUUID } from "crypto";
import type { CSVImportResult, Lead } from "@/lib/zrai/types";

export type ImportableLeadPayload = {
  id?: string;
  company_name: string;
  domain: string;
  niche?: string;
  verified_fit?: string;
  geo?: string;
  source?: string;
  source_label?: string;
  contacts?: Array<{
    name?: string;
    email?: string;
    phone?: string;
    linkedin_url?: string;
    title?: string;
  }>;
};

type StoredLeadRow = {
  lead_id: string;
  business_name: string;
  category: string | null;
  location: string | null;
  website: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

function getSupabaseConfig() {
  if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
    throw new Error(
      "Supabase bridge env is missing. SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required."
    );
  }

  return {
    url: SUPABASE_URL.replace(/\/+$/, ""),
    key: SUPABASE_SERVICE_ROLE_KEY,
  };
}

function normalizeDomain(domain: string) {
  const trimmed = String(domain || "").trim();
  if (!trimmed) {
    return "";
  }

  try {
    const withProtocol = /^https?:\/\//i.test(trimmed)
      ? trimmed
      : `https://${trimmed}`;
    const parsed = new URL(withProtocol);
    return parsed.hostname.replace(/^www\./i, "").toLowerCase();
  } catch {
    return trimmed
      .replace(/^https?:\/\//i, "")
      .replace(/^www\./i, "")
      .split("/")[0]
      .trim()
      .toLowerCase();
  }
}

function normalizeLocation(value: string | undefined) {
  return String(value || "").trim();
}

function buildStorageRow(lead: ImportableLeadPayload): Record<string, unknown> {
  const now = new Date().toISOString();
  const website = normalizeDomain(lead.domain);
  const niche = lead.verified_fit || lead.niche || "unknown";
  const location = normalizeLocation(lead.geo);
  const primaryPhone =
    lead.contacts?.find((contact) => contact.phone?.trim())?.phone?.trim() || null;
  const emails = Array.from(
    new Set(
      (lead.contacts || [])
        .map((contact) => contact.email?.trim())
        .filter((value): value is string => Boolean(value))
    )
  );

  return {
    lead_id: randomUUID(),
    business_name: lead.company_name.trim(),
    category: niche,
    location,
    geo_tags: location ? [location, niche] : [niche],
    website,
    landing_page_url: website ? `https://${website}` : null,
    phone: primaryPhone,
    emails_found: emails,
    facebook_page: null,
    instagram: null,
    ads_active: false,
    ad_start_date: null,
    ad_last_seen: null,
    cta_type: null,
    lead_form_detected: false,
    lead_lifecycle_state: "NEW",
    reviews_count: null,
    rating: null,
    created_at: now,
    updated_at: now,
  };
}

function mapStoredLeadToFrontendLead(
  row: StoredLeadRow,
  input: ImportableLeadPayload
): Lead {
  const now = new Date().toISOString();

  return {
    id: row.lead_id,
    company_name: row.business_name,
    domain: row.website || normalizeDomain(input.domain),
    niche: input.niche || row.category || "unknown",
    geo: row.location || input.geo || "",
    status: "discovered",
    verified_fit: input.verified_fit || input.niche || row.category || "unknown",
    source: input.source || input.source_label || "lead_os_preview_import",
    source_label: input.source_label || input.source || "lead_os_preview_import",
    contacts: (input.contacts || []).map((contact, index) => ({
      id: `${row.lead_id}-contact-${index}`,
      lead_id: row.lead_id,
      name: contact.name || "",
      title: contact.title,
      email: contact.email,
      phone: contact.phone,
      linkedin_url: contact.linkedin_url,
      is_primary: index === 0,
      created_at: row.created_at || now,
    })),
    intent_signals: [],
    created_at: row.created_at || now,
    updated_at: row.updated_at || now,
    analysis_state: "preview",
  };
}

async function supabaseFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const { url, key } = getSupabaseConfig();
  const response = await fetch(`${url}${path}`, {
    ...init,
    headers: {
      apikey: key,
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
      Prefer: "return=representation",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(
      `Supabase lead bridge failed (${response.status}): ${body || response.statusText}`
    );
  }

  return (await response.json()) as T;
}

async function findExistingLead(
  lead: ImportableLeadPayload
): Promise<StoredLeadRow | null> {
  const businessName = encodeURIComponent(lead.company_name.trim());
  const location = encodeURIComponent(normalizeLocation(lead.geo));
  const website = normalizeDomain(lead.domain);

  if (website) {
    const byWebsite = await supabaseFetch<StoredLeadRow[]>(
      `/rest/v1/leads?select=lead_id,business_name,category,location,website,created_at,updated_at&website=eq.${encodeURIComponent(
        website
      )}&limit=1`
    );
    if (byWebsite[0]) {
      return byWebsite[0];
    }
  }

  const byNameAndLocation = await supabaseFetch<StoredLeadRow[]>(
    `/rest/v1/leads?select=lead_id,business_name,category,location,website,created_at,updated_at&business_name=eq.${businessName}&location=eq.${location}&limit=1`
  );

  return byNameAndLocation[0] || null;
}

async function insertLead(lead: ImportableLeadPayload): Promise<StoredLeadRow> {
  const payload = buildStorageRow(lead);
  const rows = await supabaseFetch<StoredLeadRow[]>("/rest/v1/leads", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  if (!rows[0]?.lead_id) {
    throw new Error("Supabase lead bridge did not return the inserted lead.");
  }

  return rows[0];
}

export async function persistImportableLead(
  lead: ImportableLeadPayload
): Promise<Lead> {
  const existing = await findExistingLead(lead);
  const stored = existing || (await insertLead(lead));
  return mapStoredLeadToFrontendLead(stored, lead);
}

export async function importLeadsToSupabase(
  leads: ImportableLeadPayload[],
  source: string
): Promise<CSVImportResult> {
  const imported: Lead[] = [];
  const errors: CSVImportResult["errors"] = [];

  for (const [index, lead] of leads.entries()) {
    try {
      const persisted = await persistImportableLead({
        ...lead,
        source: lead.source || source,
        source_label: lead.source_label || source,
      });
      imported.push(persisted);
    } catch (error) {
      errors.push({
        row: index + 1,
        error: error instanceof Error ? error.message : "Unknown import error",
      });
    }
  }

  return {
    success: errors.length === 0,
    total_rows: leads.length,
    imported: imported.length,
    failed: errors.length,
    errors,
    leads: imported,
  };
}
