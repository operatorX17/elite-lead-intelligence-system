import { ZRAI_ENDPOINTS } from "@/lib/zrai/constants";
import type { Contact, Lead } from "@/lib/zrai/types";

function extractImportContacts(contacts: Contact[] | undefined) {
  return (contacts || [])
    .map((contact) => ({
      name: contact.name || undefined,
      email: contact.email || undefined,
      phone: contact.phone || undefined,
      linkedin_url: contact.linkedin_url || undefined,
      title: contact.title || undefined,
    }))
    .filter(
      (contact) =>
        Boolean(
          contact.name ||
            contact.email ||
            contact.phone ||
            contact.linkedin_url ||
            contact.title
        )
    );
}

export function isUuidLeadId(leadId: string | null | undefined) {
  if (!leadId) {
    return false;
  }

  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    leadId
  );
}

export async function ensurePersistedLead(lead: Lead): Promise<Lead> {
  if (!lead?.id) {
    throw new Error("Lead is missing an id.");
  }

  if (isUuidLeadId(lead.id)) {
    return lead;
  }

  if (!lead.company_name?.trim()) {
    throw new Error("Discovered lead is missing a company name.");
  }

  if (!lead.domain?.trim()) {
    throw new Error("Discovered lead is missing a domain.");
  }

  const response = await fetch(ZRAI_ENDPOINTS.import, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      source: lead.source || lead.source_label || "lead_os_preview_import",
      leads: [
        {
          company_name: lead.company_name,
          domain: lead.domain,
          niche: lead.verified_fit || lead.niche || undefined,
          geo: lead.geo || undefined,
          contacts: extractImportContacts(lead.contacts),
        },
      ],
    }),
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  const payload = await response.json();
  const importedLead =
    payload?.data?.leads?.[0] ||
    payload?.leads?.[0] ||
    payload?.data?.items?.[0] ||
    null;

  if (!importedLead?.id) {
    throw new Error("Lead import succeeded but did not return a usable lead.");
  }

  return importedLead as Lead;
}
