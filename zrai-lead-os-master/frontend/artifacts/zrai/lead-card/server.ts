/**
 * ZRAI Lead Card Artifact - Server Component
 * 
 * Handles lead card document creation and updates.
 */

import { createDocumentHandler } from "@/lib/artifacts/server";

export const leadCardDocumentHandler = createDocumentHandler<"lead-card">({
  kind: "lead-card",
  onCreateDocument: async ({ title, dataStream }) => {
    // Lead cards are typically created from tool results, not directly
    // Return empty content - will be populated by tool execution
    (dataStream as any).write({
      type: "data-leadCard",
      data: null,
      transient: true,
    });
    
    return JSON.stringify({
      company_name: title,
      domain: "",
      niche: "",
      geo: "",
      status: "discovered",
      contacts: [],
      intent_signals: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  },
  onUpdateDocument: async ({ document, description, dataStream }) => {
    // Parse existing content and update based on description
    let lead = {};
    try {
      lead = JSON.parse(document.content || "{}");
    } catch {
      // Ignore parse errors
    }

    const updatedLead = {
      ...lead,
      updated_at: new Date().toISOString(),
    };

    (dataStream as any).write({
      type: "data-leadCard",
      data: updatedLead,
      transient: true,
    });

    return JSON.stringify(updatedLead);
  },
});
